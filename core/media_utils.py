"""Media fayllar bilan ishlash. Fayllar HECH QACHON qayta kodlanmaydi yoki siqilmaydi —
bu yerda faqat o'lcham (eni/bo'yi/davomiyligi) o'qiladi."""
import json
import logging
import mimetypes
import os
import re
import subprocess

from django.conf import settings
from django.utils.text import slugify

log = logging.getLogger(__name__)

IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "webp", "gif", "avif"]
VIDEO_EXTENSIONS = ["mp4", "webm", "mov", "m4v"]
MEDIA_EXTENSIONS = IMAGE_EXTENSIONS + VIDEO_EXTENSIONS

for _type, _ext in [
    ("video/mp4", ".mp4"),
    ("video/mp4", ".m4v"),
    ("video/webm", ".webm"),
    ("video/quicktime", ".mov"),
    ("image/webp", ".webp"),
    ("image/avif", ".avif"),
]:
    mimetypes.add_type(_type, _ext)


def extension(name):
    return os.path.splitext(name or "")[1].lower().lstrip(".")


def detect_kind(name):
    ext = extension(name)
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in VIDEO_EXTENSIONS:
        return "video"
    return "file"


def guess_mime(name):
    return mimetypes.guess_type(name)[0] or "application/octet-stream"


def probe_image(path):
    """(eni, bo'yi) — EXIF burilishini hisobga olgan holda, brauzer ko'rsatganidek."""
    from PIL import Image

    try:
        with Image.open(path) as img:
            width, height = img.size
            try:
                orientation = img.getexif().get(274)
            except Exception:
                orientation = None
            if orientation in (5, 6, 7, 8):
                width, height = height, width
            return width, height, None
    except Exception as exc:  # HEIC kabi formatlar yoki buzilgan fayl
        log.info("Rasm o'lchamini o'qib bo'lmadi (%s): %s", path, exc)
        return None, None, None


def probe_video(path):
    """ffprobe orqali (eni, bo'yi, davomiylik). ffprobe bo'lmasa — (None, None, None)."""
    if not settings.FFPROBE_PATH:
        return None, None, None
    cmd = [
        settings.FFPROBE_PATH,
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height:stream_tags=rotate:stream_side_data=rotation:format=duration",
        "-of", "json",
        str(path),
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=60, check=True).stdout
        data = json.loads(out or b"{}")
    except Exception as exc:
        log.info("ffprobe ishlamadi (%s): %s", path, exc)
        return None, None, None

    stream = (data.get("streams") or [{}])[0]
    width, height = stream.get("width"), stream.get("height")
    rotation = 0
    try:
        rotation = int(float((stream.get("tags") or {}).get("rotate", 0)))
    except (TypeError, ValueError):
        pass
    for side in stream.get("side_data_list") or []:
        if "rotation" in side:
            try:
                rotation = int(float(side["rotation"]))
            except (TypeError, ValueError):
                pass
    if width and height and abs(rotation) % 180 == 90:
        width, height = height, width
    try:
        duration = float((data.get("format") or {}).get("duration"))
    except (TypeError, ValueError):
        duration = None
    return width, height, duration


CYRILLIC_TO_LATIN = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "j",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "x", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "", "ы": "i", "ь": "", "э": "e", "ю": "yu",
    "я": "ya", "ў": "o", "қ": "q", "ғ": "g", "ҳ": "h",
}


def make_slug(text, max_length=80):
    text = (text or "").lower()
    text = "".join(CYRILLIC_TO_LATIN.get(ch, ch) for ch in text)
    text = re.sub(r"[ʻʼ'`‘’]", "", text)  # o'zbek apostroflari: "o'zbek" -> "ozbek"
    return slugify(text)[:max_length].strip("-")


def unique_slug(instance, text, fallback):
    base = make_slug(text) or fallback
    model = type(instance)
    slug, n = base, 2
    while model.objects.filter(slug=slug).exclude(pk=instance.pk).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug
