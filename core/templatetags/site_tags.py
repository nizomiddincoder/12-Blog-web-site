from django import template
from django.utils.html import format_html

register = template.Library()


@register.filter
def icon(value):
    """'bi-code-slash' -> Bootstrap ikonka, aks holda emoji/matn sifatida chiqaradi."""
    value = (value or "").strip()
    if value.startswith("bi-"):
        return format_html('<i class="bi {}" aria-hidden="true"></i>', value)
    return value


@register.filter
def aspect(media):
    """Media uchun CSS aspect-ratio qiymati (sahifa sakrab ketmasligi uchun)."""
    if getattr(media, "width", None) and getattr(media, "height", None):
        return f"{media.width} / {media.height}"
    return "auto"
