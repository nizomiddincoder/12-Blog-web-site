"""Barcha platformalar uchun umumiy qism."""
import logging
import time
from dataclasses import dataclass, field

import requests
from django.conf import settings

log = logging.getLogger("core.publishers")


class PublishError(Exception):
    """Platformaga yuborishda xatolik (admin panelda ko'rsatiladi)."""


class Skip(Exception):
    """Post bu platformaga mos emas (masalan, Instagram'ga matnsiz post)."""


@dataclass
class Result:
    ids: list
    url: str = ""
    warnings: list = field(default_factory=list)


def public_site_url():
    """Internetdan ochiladigan sayt manzili yoki bo'sh satr (lokalda)."""
    url = settings.SITE_URL
    if not url or "localhost" in url or "127.0.0.1" in url:
        return ""
    return url


def site_link(post):
    from core.models import SiteSettings

    base = public_site_url()
    if not base or not SiteSettings.load().add_site_link:
        return ""
    return base + post.get_absolute_url()


def redact(text, *secrets):
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    return text


def http(method, url, *, secrets=(), retries=3, timeout=(20, 900), **kwargs):
    """requests so'rovi: aloqa uzilsa yoki 429/5xx bo'lsa qayta urinadi. Xatoni PublishError qiladi."""
    for attempt in range(retries + 1):
        try:
            response = requests.request(method, url, timeout=timeout, **kwargs)
        except requests.RequestException as exc:
            if attempt < retries:
                time.sleep(3 * (attempt + 1))
                continue
            raise PublishError(redact(f"Aloqa o'rnatilmadi: {exc}", *secrets)) from None
        if response.status_code == 429 or response.status_code >= 500:
            if attempt < retries:
                wait = int(response.headers.get("Retry-After", 0) or 0) or 5 * (attempt + 1)
                time.sleep(min(wait, 60))
                continue
        if response.status_code >= 400:
            raise PublishError(redact(f"HTTP {response.status_code}: {_error_text(response)}", *secrets))
        return response


def _error_text(response):
    try:
        data = response.json()
    except ValueError:
        return response.text[:300]
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict):
            return err.get("error_user_msg") or err.get("message") or str(err)
        return data.get("message") or data.get("error_description") or str(err or data)[:300]
    return str(data)[:300]


def cut(text, limit):
    """Matnni so'z chegarasida qisqartiradi."""
    if len(text) <= limit:
        return text
    text = text[: max(limit - 1, 0)]
    space = text.rfind(" ")
    if space > len(text) * 0.7:
        text = text[:space]
    return text.rstrip() + "…"


class Publisher:
    key = ""
    label = ""
    can_delete = False
    uses_oauth = False
    setup_hint = ""

    def keys_present(self):
        """.env dagi kalitlar bormi."""
        return True

    def account(self):
        from core.models import SocialAccount

        return SocialAccount.objects.filter(platform=self.key).first()

    def problem(self):
        """Ishlashga nima to'sqinlik qilyapti (bo'sh satr — hammasi joyida)."""
        if not self.keys_present():
            return self.setup_hint
        if self.uses_oauth:
            account = self.account()
            if not account:
                return "Akkaunt ulanmagan"
            if account.is_expired:
                return "Ulanish muddati tugagan — qayta ulang"
        return ""

    def is_ready(self):
        return not self.problem()

    def publish(self, post):
        raise NotImplementedError

    def delete(self, delivery):
        raise PublishError(f"{self.label} postlarni API orqali o'chirishni qo'llab-quvvatlamaydi.")

    # OAuth
    def authorize_url(self, redirect_uri, state):
        raise NotImplementedError

    def finish_auth(self, code, redirect_uri):
        raise NotImplementedError
