"""LinkedIn shaxsiy profil (Posts API, ruxsat: w_member_social).

Cheklovlar: bitta postda yoki bitta video, yoki 1–20 ta rasm (JPG/PNG/GIF). Matn — 3000 belgigacha.
Ulanish 60 kun amal qiladi, so'ng admin paneldan "Qayta ulash" bosiladi.
"""
import re
import time
from datetime import timedelta
from urllib.parse import quote, urlencode

from django.conf import settings
from django.utils import timezone

from core.media_utils import extension

from .base import PublishError, Publisher, Result, cut, http, site_link

AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
API = "https://api.linkedin.com"
SCOPES = "openid profile w_member_social"
IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif"}
TEXT_LIMIT = 3000

# LinkedIn "little text" formatidagi maxsus belgilar — oldiga \ qo'yilmasa matn kesilib qoladi.
RESERVED = re.compile(r"([\\|{}@\[\]()<>#*_~])")
HASHTAG = re.compile(r"(?<![\w&])#(\w+)")


def escape_little_text(text):
    """Matnni LinkedIn formatiga o'tkazadi; #teglar haqiqiy hashtag bo'lib qoladi."""
    out, pos = [], 0
    for match in HASHTAG.finditer(text):
        out.append(RESERVED.sub(r"\\\1", text[pos:match.start()]))
        out.append("{hashtag|\\#|" + match.group(1) + "}")
        pos = match.end()
    out.append(RESERVED.sub(r"\\\1", text[pos:]))
    return "".join(out)


def build_commentary(post, link):
    title = post.title.strip()
    body = (post.content or "").strip()
    tail = f"\n\n{link}" if link else ""
    room = TEXT_LIMIT - len(title) - len(tail) - 2
    body = cut(body, room) if body else ""
    text = title + (f"\n\n{body}" if body else "")
    return escape_little_text(text) + tail


class LinkedInPublisher(Publisher):
    key = "linkedin"
    label = "LinkedIn"
    can_delete = True
    uses_oauth = True
    setup_hint = "LINKEDIN_CLIENT_ID va LINKEDIN_CLIENT_SECRET ko'rsatilmagan"

    def keys_present(self):
        return bool(settings.LINKEDIN_CLIENT_ID and settings.LINKEDIN_CLIENT_SECRET)

    # ------------------------------------------------------------------ OAuth
    def authorize_url(self, redirect_uri, state):
        params = {
            "response_type": "code",
            "client_id": settings.LINKEDIN_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": SCOPES,
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    def finish_auth(self, code, redirect_uri):
        secret = settings.LINKEDIN_CLIENT_SECRET
        token = http("POST", TOKEN_URL, secrets=(secret, code), data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": settings.LINKEDIN_CLIENT_ID,
            "client_secret": secret,
        }).json()
        access = token["access_token"]
        me = http("GET", f"{API}/v2/userinfo", secrets=(access,),
                  headers={"Authorization": f"Bearer {access}"}).json()
        return {
            "account_id": me["sub"],
            "account_name": me.get("name", ""),
            "access_token": access,
            "refresh_token": token.get("refresh_token", ""),
            "expires_at": timezone.now() + timedelta(seconds=int(token.get("expires_in", 5184000))),
        }

    # ------------------------------------------------------------------ API
    def _headers(self, token, json_body=True):
        headers = {
            "Authorization": f"Bearer {token}",
            "LinkedIn-Version": settings.LINKEDIN_API_VERSION,
            "X-Restli-Protocol-Version": "2.0.0",
        }
        if json_body:
            headers["Content-Type"] = "application/json"
        return headers

    def _token(self):
        account = self.account()
        if not account:
            raise PublishError("LinkedIn akkaunti ulanmagan.")
        if account.is_expired:
            raise PublishError("LinkedIn ulanish muddati tugagan — admin panelda qayta ulang.")
        return account

    def _upload_image(self, token, author, media):
        init = http("POST", f"{API}/rest/images?action=initializeUpload", secrets=(token,),
                    headers=self._headers(token),
                    json={"initializeUploadRequest": {"owner": author}}).json()["value"]
        with media.file.open("rb") as fh:
            data = fh.read()
        http("PUT", init["uploadUrl"], secrets=(token,), headers={"Authorization": f"Bearer {token}"}, data=data)
        return init["image"]

    def _upload_video(self, token, author, media):
        size = media.file.size
        init = http("POST", f"{API}/rest/videos?action=initializeUpload", secrets=(token,),
                    headers=self._headers(token),
                    json={"initializeUploadRequest": {
                        "owner": author, "fileSizeBytes": size,
                        "uploadCaptions": False, "uploadThumbnail": False,
                    }}).json()["value"]
        video_urn = init["video"]
        etags = []
        with media.file.open("rb") as fh:
            for part in init["uploadInstructions"]:
                first, last = int(part["firstByte"]), int(part["lastByte"])
                fh.seek(first)
                chunk = fh.read(last - first + 1)
                resp = http("PUT", part["uploadUrl"], secrets=(token,),
                            headers={"Content-Type": "application/octet-stream"}, data=chunk)
                etags.append(resp.headers.get("ETag", "").strip('"'))
        http("POST", f"{API}/rest/videos?action=finalizeUpload", secrets=(token,),
             headers=self._headers(token),
             json={"finalizeUploadRequest": {
                 "video": video_urn, "uploadToken": init.get("uploadToken", ""), "uploadedPartIds": etags,
             }})
        # LinkedIn videoni qayta ishlaydi — tayyor bo'lishini kutamiz (ko'pi bilan ~15 daqiqa).
        for _ in range(180):
            info = http("GET", f"{API}/rest/videos/{quote(video_urn, safe='')}", secrets=(token,),
                        headers=self._headers(token, json_body=False)).json()
            status = info.get("status")
            if status == "AVAILABLE":
                return video_urn
            if status == "PROCESSING_FAILED":
                raise PublishError(f"LinkedIn videoni qayta ishlay olmadi: {info.get('processingFailureReason', '')}")
            time.sleep(5)
        raise PublishError("LinkedIn videoni qayta ishlash juda uzoq davom etdi.")

    def publish(self, post):
        account = self._token()
        token = account.access_token
        author = f"urn:li:person:{account.account_id}"
        warnings = []

        media = list(post.media.all())
        videos = [m for m in media if m.is_video]
        images = [m for m in media if m.is_image]
        unsupported = [m for m in images if extension(m.file.name) not in IMAGE_EXTENSIONS]
        images = [m for m in images if m not in unsupported]
        if unsupported:
            warnings.append("LinkedIn qabul qilmaydigan format (faqat JPG/PNG/GIF): "
                            + ", ".join(m.filename for m in unsupported))

        content = None
        if videos:
            if len(videos) > 1 or images:
                warnings.append("LinkedIn bitta postda faqat bitta video qabul qiladi — birinchi video yuborildi.")
            urn = self._upload_video(token, author, videos[0])
            content = {"media": {"id": urn, "title": post.title[:200]}}
        elif images:
            if len(images) > 20:
                warnings.append("LinkedIn ko'pi bilan 20 ta rasm qabul qiladi — birinchi 20 tasi yuborildi.")
                images = images[:20]
            urns = [self._upload_image(token, author, m) for m in images]
            if len(urns) == 1:
                content = {"media": {"id": urns[0], "altText": (images[0].caption or post.title)[:120]}}
            else:
                content = {"multiImage": {"images": [
                    {"id": u, "altText": (m.caption or post.title)[:120]} for u, m in zip(urns, images)
                ]}}

        body = {
            "author": author,
            "commentary": build_commentary(post, site_link(post)),
            "visibility": "PUBLIC",
            "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        if content:
            body["content"] = content
        resp = http("POST", f"{API}/rest/posts", secrets=(token,), headers=self._headers(token), json=body)
        post_urn = resp.headers.get("x-restli-id", "")
        url = f"https://www.linkedin.com/feed/update/{post_urn}/" if post_urn else ""
        return Result([post_urn] if post_urn else [], url, warnings)

    def delete(self, delivery):
        account = self._token()
        for urn in delivery.external_ids:
            http("DELETE", f"{API}/rest/posts/{quote(urn, safe='')}", secrets=(account.access_token,),
                 headers=self._headers(account.access_token, json_body=False))
