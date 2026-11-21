"""Admin paneldagi belgilar uchun haqiqiy sayt favicon'lari (ikonka/stiker o'rniga)."""
from urllib.parse import urlparse

from django.utils.html import format_html

PLATFORM_DOMAINS = {
    "telegram": "telegram.org",
    "linkedin": "linkedin.com",
    "instagram": "instagram.com",
    "github": "github.com",
    "youtube": "youtube.com",
    "facebook": "facebook.com",
    "x": "x.com",
}

FAVICON_SERVICE = "https://www.google.com/s2/favicons?domain={host}&sz={size}"


def host_of(target):
    """'telegram' / 'https://t.me/kanal' / 'example.com' -> domen nomi."""
    target = (target or "").strip()
    if not target:
        return ""
    if target in PLATFORM_DOMAINS:
        return PLATFORM_DOMAINS[target]
    if "//" not in target:
        target = "//" + target
    return (urlparse(target).hostname or "").removeprefix("www.")


def favicon_src(target, size=64):
    host = host_of(target)
    return FAVICON_SERVICE.format(host=host, size=size) if host else ""


def favicon_img(target, size=18, css_class=""):
    src = favicon_src(target)
    if not src:
        return ""
    return format_html(
        '<img class="ds-fav {}" src="{}" width="{}" height="{}" alt="" loading="lazy" referrerpolicy="no-referrer">',
        css_class, src, size, size,
    )
