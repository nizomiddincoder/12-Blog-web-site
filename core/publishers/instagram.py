"""Instagram Business akkaunt (Instagram API with Instagram Login).

Qanday ishlaydi: Instagram faylni bizning saytimizdagi ochiq havoladan O'ZI yuklab oladi —
shuning uchun sayt internetda (HTTPS) bo'lishi shart.

Cheklovlar:
  * matnsiz (rasmsiz/videosiz) post bo'lmaydi;
  * rasm faqat JPEG va nisbati 4:5 … 1.91:1 bo'lishi kerak. Mos kelmasa, FAQAT Instagram uchun
    alohida JPEG nusxa yasaladi (oq hoshiya bilan) — saytdagi asl fayl o'zgarmaydi;
  * karusel — 10 tagacha rasm/video; bitta video Reels bo'lib chiqadi;
  * izoh 2200 belgigacha, matndagi havola bosilmaydi;
  * kuniga 50 tagacha post.
"""
import os
import time
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from core.media_utils import extension

from .base import PublishError, Publisher, Result, Skip, cut, http, public_site_url, site_link

AUTH_URL = "https://www.instagram.com/oauth/authorize"
TOKEN_URL = "https://api.instagram.com/oauth/access_token"
GRAPH = "https://graph.instagram.com"
SCOPES = "instagram_business_basic,instagram_business_content_publish"
CAPTION_LIMIT = 2200
MIN_RATIO, MAX_RATIO = 4 / 5, 1.91
JPEG_MAX_BYTES = 8 * 1024 * 1024


def build_caption(post, link):
    title = post.title.strip()
    body = (post.content or "").strip()
    tail = f"\n\nBatafsil: {link}" if link else ""
    room = CAPTION_LIMIT - len(title) - len(tail) - 2
    body = cut(body, room) if body else ""
    return title + (f"\n\n{body}" if body else "") + tail


def instagram_image_name(media):
    """Instagram uchun JPEG nusxa kerakmi? Kerak bo'lsa — yaratib, nomini qaytaradi; aks holda asl nomini."""
    ext = extension(media.file.name)
    ratio = (media.width / media.height) if media.width and media.height else None
    ok_ratio = ratio is None or (MIN_RATIO - 0.01) <= ratio <= (MAX_RATIO + 0.01)
    if ext in ("jpg", "jpeg") and ok_ratio and media.file.size <= JPEG_MAX_BYTES:
        return media.file.name

    from PIL import Image, ImageOps

    storage = media.file.storage
    stem = os.path.splitext(os.path.basename(media.file.name))[0]
    name = f"instagram/{media.pk}-{stem}.jpg"
    if storage.exists(name):
        return name
    with media.file.open("rb") as fh, Image.open(fh) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        w, h = img.size
        r = w / h
        if r < MIN_RATIO:      # juda tik — yon tomonlarga oq hoshiya
            new_w, new_h = round(h * MIN_RATIO), h
        elif r > MAX_RATIO:    # juda yotiq — tepa-pastga oq hoshiya
            new_w, new_h = w, round(w / MAX_RATIO)
        else:
            new_w, new_h = w, h
        if (new_w, new_h) != (w, h):
            canvas = Image.new("RGB", (new_w, new_h), (255, 255, 255))
            canvas.paste(img, ((new_w - w) // 2, (new_h - h) // 2))
            img = canvas
        from io import BytesIO
        for quality in (95, 90, 85):
            buf = BytesIO()
            img.save(buf, "JPEG", quality=quality, subsampling=0)
            if buf.tell() <= JPEG_MAX_BYTES:
                break
    storage.save(name, ContentFile(buf.getvalue()))
    return name


class InstagramPublisher(Publisher):
    key = "instagram"
    label = "Instagram"
    can_delete = False
    setup_hint = "MAKE_INSTAGRAM_WEBHOOK_URL (yoki INSTAGRAM_APP_ID/SECRET) ko'rsatilmagan"

    @property
    def via_webhook(self):
        """Make.com orqali yuborish rejimi (Meta developer akkaunti kerak emas)."""
        return bool(settings.MAKE_INSTAGRAM_WEBHOOK_URL)

    @property
    def uses_oauth(self):
        return not self.via_webhook

    def keys_present(self):
        return self.via_webhook or bool(settings.INSTAGRAM_APP_ID and settings.INSTAGRAM_APP_SECRET)

    def problem(self):
        problem = super().problem()
        if not problem and not public_site_url():
            return "Sayt internetda emas (SITE_URL) — Instagram faylni saytdan yuklab oladi"
        return problem

    def _url(self, path):
        return f"{GRAPH}/{settings.INSTAGRAM_API_VERSION}/{path}"

    # ------------------------------------------------------------------ OAuth
    def authorize_url(self, redirect_uri, state):
        params = {
            "client_id": settings.INSTAGRAM_APP_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": SCOPES,
            "state": state,
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    def finish_auth(self, code, redirect_uri):
        code = code.split("#")[0]
        secret = settings.INSTAGRAM_APP_SECRET
        short = http("POST", TOKEN_URL, secrets=(secret, code), data={
            "client_id": settings.INSTAGRAM_APP_ID,
            "client_secret": secret,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code": code,
        }).json()
        if "data" in short and isinstance(short["data"], list):
            short = short["data"][0]
        long = http("GET", f"{GRAPH}/access_token", secrets=(secret, short["access_token"]), params={
            "grant_type": "ig_exchange_token",
            "client_secret": secret,
            "access_token": short["access_token"],
        }).json()
        access = long["access_token"]
        me = http("GET", self._url("me"), secrets=(access,),
                  params={"fields": "user_id,username", "access_token": access}).json()
        return {
            "account_id": str(me.get("user_id") or me.get("id") or short.get("user_id")),
            "account_name": "@" + me.get("username", ""),
            "access_token": access,
            "refresh_token": "",
            "expires_at": timezone.now() + timedelta(seconds=int(long.get("expires_in", 5184000))),
        }

    def _account(self):
        account = self.account()
        if not account:
            raise PublishError("Instagram akkaunti ulanmagan.")
        if account.is_expired:
            raise PublishError("Instagram ulanish muddati tugagan — admin panelda qayta ulang.")
        # 60 kunlik token: 20 kundan kam qolsa avtomatik yangilaymiz.
        if account.days_left is not None and account.days_left < 20 and \
                timezone.now() - account.updated_at > timedelta(days=1):
            try:
                data = http("GET", f"{GRAPH}/refresh_access_token", secrets=(account.access_token,), params={
                    "grant_type": "ig_refresh_token", "access_token": account.access_token,
                }).json()
                account.access_token = data["access_token"]
                account.expires_at = timezone.now() + timedelta(seconds=int(data.get("expires_in", 5184000)))
                account.save(update_fields=["access_token", "expires_at", "updated_at"])
            except PublishError:
                pass
        return account

    # ------------------------------------------------------------------ API
    def _create(self, account, **params):
        params["access_token"] = account.access_token
        return http("POST", self._url(f"{account.account_id}/media"), secrets=(account.access_token,),
                    data=params).json()["id"]

    def _wait(self, account, container_id, timeout=900):
        deadline = time.monotonic() + timeout
        while True:
            info = http("GET", self._url(container_id), secrets=(account.access_token,), params={
                "fields": "status_code,status", "access_token": account.access_token,
            }).json()
            status = info.get("status_code")
            if status in ("FINISHED", "PUBLISHED"):
                return
            if status in ("ERROR", "EXPIRED"):
                raise PublishError(f"Instagram faylni qabul qilmadi: {info.get('status') or status}")
            if time.monotonic() > deadline:
                raise PublishError("Instagram faylni qayta ishlashi juda uzoq davom etdi.")
            time.sleep(5)

    def _media_url(self, media):
        base = public_site_url()
        if media.is_image:
            name = instagram_image_name(media)
            return base + media.file.storage.url(name)
        return base + media.file.url

    # ------------------------------------------------------------------ Make.com
    def build_payload(self, post, media, caption, test=False):
        """Make.com uchun JSON. type: photo (1 rasm) / reel (1 video) / carousel (2–10 ta)."""
        items = []
        for m in media:
            url = self._media_url(m)
            items.append({
                "media_type": "VIDEO" if m.is_video else "IMAGE",
                "url": url,
                "image_url": "" if m.is_video else url,
                "video_url": url if m.is_video else "",
            })
        if len(items) == 1:
            kind = "reel" if items[0]["media_type"] == "VIDEO" else "photo"
        else:
            kind = "carousel"
        return {
            "platform": "instagram",
            "type": kind,
            "test": test,
            "post_id": post.pk,
            "title": post.title,
            "caption": caption,
            "link": site_link(post),
            "image_url": next((i["image_url"] for i in items if i["image_url"]), ""),
            "video_url": next((i["video_url"] for i in items if i["video_url"]), ""),
            "media": items,
        }

    def _post_webhook(self, payload):
        resp = http("POST", settings.MAKE_INSTAGRAM_WEBHOOK_URL, json=payload,
                    secrets=(settings.MAKE_INSTAGRAM_WEBHOOK_URL,), retries=2, timeout=(20, 200))
        try:
            data = resp.json()
        except ValueError:
            data = {}
        return (data.get("permalink") or data.get("url") or "") if isinstance(data, dict) else ""

    def send_sample(self):
        """Make'ga namunaviy ma'lumot yuboradi — Make ma'lumot tuzilishini o'rganib olishi uchun."""
        from core.models import Post

        post = next((p for p in Post.objects.published().prefetch_related("media")[:30]
                     if sum(1 for m in p.media.all() if m.is_image or m.is_video) >= 2), None)
        if post:
            media = [m for m in post.media.all() if m.is_image or m.is_video][:10]
            payload = self.build_payload(post, media, build_caption(post, site_link(post)), test=True)
        else:
            base = public_site_url() or "https://example.com"
            payload = {
                "platform": "instagram", "type": "carousel", "test": True, "post_id": 0,
                "title": "Namuna post", "caption": "Namuna matn", "link": base + "/blog/namuna/",
                "image_url": base + "/media/namuna.jpg", "video_url": base + "/media/namuna.mp4",
                "media": [
                    {"media_type": "IMAGE", "url": base + "/media/namuna.jpg",
                     "image_url": base + "/media/namuna.jpg", "video_url": ""},
                    {"media_type": "VIDEO", "url": base + "/media/namuna.mp4",
                     "image_url": "", "video_url": base + "/media/namuna.mp4"},
                ],
            }
        self._post_webhook(payload)
        return payload

    # ------------------------------------------------------------------ Yuborish
    def publish(self, post):
        if not public_site_url():
            raise PublishError("Instagram uchun sayt internetda bo'lishi kerak (SITE_URL).")
        media = [m for m in post.media.all() if m.is_image or m.is_video]
        if not media:
            raise Skip("Instagram rasm yoki videosiz post qabul qilmaydi.")
        warnings = []
        if len(media) > 10:
            warnings.append("Instagram karuselida ko'pi bilan 10 ta fayl — birinchi 10 tasi yuborildi.")
            media = media[:10]
        caption = build_caption(post, site_link(post))

        if self.via_webhook:
            url = self._post_webhook(self.build_payload(post, media, caption))
            warnings.append("Make.com'ga topshirildi. Instagram'ga chiqqanini Make → History bo'limida ko'rasiz.")
            return Result([], url, warnings)

        account = self._account()
        if len(media) == 1:
            m = media[0]
            if m.is_video:
                container = self._create(account, media_type="REELS", video_url=self._media_url(m),
                                         caption=caption, share_to_feed="true")
            else:
                container = self._create(account, image_url=self._media_url(m), caption=caption)
        else:
            children = []
            for m in media:
                if m.is_video:
                    child = self._create(account, media_type="VIDEO", video_url=self._media_url(m),
                                         is_carousel_item="true")
                else:
                    child = self._create(account, image_url=self._media_url(m), is_carousel_item="true")
                self._wait(account, child)
                children.append(child)
            container = self._create(account, media_type="CAROUSEL", children=",".join(children), caption=caption)
        self._wait(account, container)

        media_id = http("POST", self._url(f"{account.account_id}/media_publish"), secrets=(account.access_token,),
                        data={"creation_id": container, "access_token": account.access_token}).json()["id"]
        url = ""
        try:
            url = http("GET", self._url(media_id), secrets=(account.access_token,), params={
                "fields": "permalink", "access_token": account.access_token,
            }).json().get("permalink", "")
        except PublishError:
            pass
        return Result([media_id], url, warnings)
