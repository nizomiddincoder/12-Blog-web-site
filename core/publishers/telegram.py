"""Telegram kanal (Bot API).

Sifat: fayllar biz tomondan siqilmaydi. Videolar sendVideo orqali — Telegram qayta kodlamaydi.
Rasmlarni Telegram "rasm" (sendPhoto) sifatida doim siqadi, shuning uchun "Asl sifatda" rejimida
rasmlar fayl (sendDocument) sifatida yuboriladi.
"""
import html
import json
import time

import requests
from django.conf import settings

from core.media_utils import extension, guess_mime

from .base import PublishError, Publisher, Result, site_link

CAPTION_LIMIT = 1024
MESSAGE_LIMIT = 4096
GROUP_LIMIT = 10
PHOTO_MAX_BYTES = 10 * 1024 * 1024
PHOTO_EXTENSIONS = {"jpg", "jpeg", "png"}

TelegramError = PublishError


def _redact(text):
    token = settings.TELEGRAM_BOT_TOKEN
    return text.replace(token, "***") if token else text


def call(method, data=None, files=None, retries=3):
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        raise PublishError("TELEGRAM_BOT_TOKEN ko'rsatilmagan.")
    url = f"{settings.TELEGRAM_API_BASE}/bot{token}/{method}"

    for attempt in range(retries + 1):
        if files:
            for value in files.values():
                value[1].seek(0)
        try:
            response = requests.post(url, data=data, files=files, timeout=(20, 1800))
        except requests.RequestException as exc:
            if attempt < retries:
                time.sleep(3 * (attempt + 1))
                continue
            raise PublishError(_redact(f"Telegram bilan aloqa o'rnatilmadi: {exc}")) from None

        try:
            payload = response.json()
        except ValueError:
            raise PublishError(f"Telegram noto'g'ri javob qaytardi (HTTP {response.status_code}).") from None

        if payload.get("ok"):
            return payload["result"]

        retry_after = (payload.get("parameters") or {}).get("retry_after")
        if retry_after and attempt < retries:
            time.sleep(int(retry_after) + 1)
            continue
        raise PublishError(_redact(payload.get("description") or f"HTTP {response.status_code}"))


def _chat_id():
    chat = settings.TELEGRAM_CHANNEL_ID
    if not chat:
        raise PublishError("TELEGRAM_CHANNEL_ID ko'rsatilmagan.")
    return chat


# --------------------------------------------------------------------------- #
#  Matn
# --------------------------------------------------------------------------- #
def _u16(text):
    """Telegram belgilarni UTF-16 birliklarida sanaydi (emoji = 2)."""
    return len(text.encode("utf-16-le")) // 2


def _cut(text, max_units):
    if max_units <= 0:
        return ""
    out, used = [], 0
    for ch in text:
        size = _u16(ch)
        if used + size > max_units:
            break
        out.append(ch)
        used += size
    result = "".join(out)
    space = result.rfind(" ")
    if space > len(result) * 0.7:
        result = result[:space]
    return result.rstrip()


def build_text(post, limit, link=""):
    """(html_matn, qisqartirildimi). Limit — ko'rinadigan belgilar soni."""
    title = post.title.strip()
    body = (post.content or "").strip()
    link_label = "Batafsil o'qish →"

    fixed = _u16(title) + (2 + _u16(link_label) if link else 0)
    sep = 2 if body else 0
    truncated = False
    if fixed + sep + _u16(body) > limit:
        body = _cut(body, limit - fixed - sep - 1)
        body = (body + "…") if body else ""
        truncated = True

    parts = [f"<b>{html.escape(title, quote=False)}</b>"]
    if body:
        parts.append(html.escape(body, quote=False))
    if link:
        parts.append(f'<a href="{html.escape(link)}">{html.escape(link_label, quote=False)}</a>')
    return "\n\n".join(parts), truncated


# --------------------------------------------------------------------------- #
#  Media
# --------------------------------------------------------------------------- #
def classify(media, mode):
    """Telegramga qaysi turda yuborish: photo / video / document / None (juda katta)."""
    try:
        size = media.file.size
    except OSError:
        return None, "fayl diskda topilmadi"
    if size > settings.TELEGRAM_MAX_UPLOAD_MB * 1024 * 1024:
        return None, f"{size / 1024 / 1024:.1f} MB — bot limiti ({settings.TELEGRAM_MAX_UPLOAD_MB} MB) dan katta"

    if media.kind == "video":
        return "video", None
    if media.kind == "image":
        if mode == "original":
            return "document", None
        if extension(media.file.name) not in PHOTO_EXTENSIONS or size > PHOTO_MAX_BYTES:
            return "document", None
        w, h = media.width, media.height
        if w and h and (w + h > 10000 or max(w, h) / min(w, h) > 20):
            return "document", None
        return "photo", None
    return "document", None


def make_batches(items):
    """Albomlar: rasm+video aralash bo'lishi mumkin, hujjatlar faqat hujjatlar bilan; max 10 ta."""
    batches, current, group = [], [], None
    for media, tg_type in items:
        g = "doc" if tg_type == "document" else "visual"
        if current and (g != group or len(current) == GROUP_LIMIT):
            batches.append(current)
            current = []
        group = g
        current.append((media, tg_type))
    if current:
        batches.append(current)
    return batches


def _media_extras(media, tg_type):
    extras = {}
    if tg_type == "video":
        extras["supports_streaming"] = True
        if media.width and media.height:
            extras["width"], extras["height"] = media.width, media.height
        if media.duration:
            extras["duration"] = int(round(media.duration))
    return extras


def _open(media, key):
    fh = media.file.storage.open(media.file.name, "rb")
    return key, (media.filename, fh, guess_mime(media.file.name))


def send_batch(batch, caption=None):
    chat = _chat_id()
    if len(batch) == 1:
        media, tg_type = batch[0]
        method = {"photo": "sendPhoto", "video": "sendVideo", "document": "sendDocument"}[tg_type]
        data = {"chat_id": chat, **_media_extras(media, tg_type)}
        if tg_type == "video":
            data["supports_streaming"] = "true"
        if caption:
            data.update(caption=caption, parse_mode="HTML")
        key, file_tuple = _open(media, tg_type)
        try:
            result = call(method, data=data, files={key: file_tuple})
        finally:
            file_tuple[1].close()
        return [result["message_id"]]

    items, files = [], {}
    try:
        for i, (media, tg_type) in enumerate(batch):
            key, file_tuple = _open(media, f"file{i}")
            files[key] = file_tuple
            item = {"type": tg_type, "media": f"attach://{key}", **_media_extras(media, tg_type)}
            if i == 0 and caption:
                item.update(caption=caption, parse_mode="HTML")
            items.append(item)
        result = call("sendMediaGroup", data={"chat_id": chat, "media": json.dumps(items)}, files=files)
    finally:
        for file_tuple in files.values():
            file_tuple[1].close()
    return [m["message_id"] for m in result]


def send_message(text):
    result = call("sendMessage", data={"chat_id": _chat_id(), "text": text, "parse_mode": "HTML"})
    return [result["message_id"]]


def delete_messages(message_ids):
    chat = _chat_id()
    ids = list(message_ids)
    for i in range(0, len(ids), 100):
        call("deleteMessages", data={"chat_id": chat, "message_ids": json.dumps(ids[i:i + 100])})


def send_post(post):
    """Postni kanalga yuboradi. Qaytaradi: (xabar_id_lari, ogohlantirishlar)."""
    from core.models import SiteSettings

    site = SiteSettings.load()
    link = site_link(post)

    items, warnings = [], []
    for media in post.media.all():
        tg_type, problem = classify(media, site.telegram_media_mode)
        if tg_type is None:
            warnings.append(f"{media.filename}: {problem}, Telegramga yuborilmadi (saytda bor).")
            continue
        items.append((media, tg_type))

    batches = make_batches(items)
    ids = []
    if not batches:
        text, _ = build_text(post, MESSAGE_LIMIT, link)
        return send_message(text), warnings

    caption, truncated = build_text(post, CAPTION_LIMIT, link)
    if not truncated:
        ids += send_batch(batches[0], caption)
        for batch in batches[1:]:
            ids += send_batch(batch)
    else:
        # Matn izoh limitiga sig'madi: avval media, keyin to'liq matn alohida xabar.
        for batch in batches:
            ids += send_batch(batch)
        text, _ = build_text(post, MESSAGE_LIMIT, link)
        ids += send_message(text)
    return ids, warnings


def check_connection():
    """Bot va kanal sozlamalarini tekshiradi. Qaytaradi: matnli hisobot qatorlari."""
    lines = []
    me = call("getMe")
    lines.append(f"✔ Bot: @{me.get('username')} (id {me['id']})")
    chat = call("getChat", data={"chat_id": _chat_id()})
    lines.append(f"✔ Kanal: {chat.get('title')} ({chat.get('id')})")
    member = call("getChatMember", data={"chat_id": _chat_id(), "user_id": me["id"]})
    if member.get("status") != "administrator":
        lines.append("✘ Bot kanalda admin emas! Kanal sozlamalaridan botni admin qiling.")
    elif not member.get("can_post_messages", False):
        lines.append("✘ Botda 'Xabar joylash' huquqi yo'q.")
    else:
        lines.append("✔ Bot kanalda admin va xabar joylay oladi.")
        if not member.get("can_delete_messages", False):
            lines.append("! Botda 'Xabarlarni o'chirish' huquqi yo'q — o'chirish va yangilash ishlamaydi.")
    return lines


class TelegramPublisher(Publisher):
    key = "telegram"
    label = "Telegram"
    can_delete = True
    setup_hint = "TELEGRAM_BOT_TOKEN va TELEGRAM_CHANNEL_ID ko'rsatilmagan"

    def keys_present(self):
        return bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHANNEL_ID)

    def publish(self, post):
        ids, warnings = send_post(post)
        url = ""
        channel = settings.TELEGRAM_CHANNEL_ID
        if channel.startswith("@") and ids:
            url = f"https://t.me/{channel[1:]}/{ids[0]}"
        return Result(ids, url, warnings)

    def delete(self, delivery):
        if delivery.external_ids:
            delete_messages(delivery.external_ids)
