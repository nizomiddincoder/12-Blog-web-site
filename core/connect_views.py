"""LinkedIn / Instagram akkauntlarini admin panel orqali ulash (OAuth)."""
import secrets

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import publishers
from .models import SocialAccount
from .publishers import PublishError


def redirect_uri(request, platform):
    base = settings.SITE_URL or request.build_absolute_uri("/").rstrip("/")
    return f"{base}{reverse('connect_callback', args=[platform])}"


def _oauth_publisher(platform):
    publisher = publishers.PUBLISHERS.get(platform)
    if not publisher or not publisher.uses_oauth:
        raise Http404
    return publisher


def _back():
    return redirect("admin:core_socialaccount_changelist")


@staff_member_required
def connect_start(request, platform):
    publisher = _oauth_publisher(platform)
    if not publisher.keys_present():
        messages.error(request, f"{publisher.label}: {publisher.setup_hint}. Qo'llanmaga qarang (ULASH.md).")
        return _back()
    state = secrets.token_urlsafe(24)
    request.session[f"oauth_state_{platform}"] = state
    return redirect(publisher.authorize_url(redirect_uri(request, platform), state))


@staff_member_required
def connect_callback(request, platform):
    publisher = _oauth_publisher(platform)
    expected = request.session.pop(f"oauth_state_{platform}", None)
    if request.GET.get("error"):
        messages.error(request, f"{publisher.label}: ulanish bekor qilindi ({request.GET.get('error_description') or request.GET['error']}).")
        return _back()
    if not expected or request.GET.get("state") != expected:
        messages.error(request, f"{publisher.label}: xavfsizlik tekshiruvidan o'tmadi, qaytadan urinib ko'ring.")
        return _back()
    code = request.GET.get("code")
    if not code:
        messages.error(request, f"{publisher.label}: javobda kod yo'q.")
        return _back()
    try:
        data = publisher.finish_auth(code, redirect_uri(request, platform))
    except (PublishError, KeyError, ValueError) as exc:
        messages.error(request, f"{publisher.label}: ulanib bo'lmadi — {exc}")
        return _back()
    SocialAccount.objects.update_or_create(platform=platform, defaults=data)
    messages.success(request, f"{publisher.label} ulandi: {data.get('account_name') or data['account_id']}")
    return _back()


@staff_member_required
@require_POST
def connect_sample(request, platform):
    """Make.com webhook'iga namunaviy ma'lumot yuboradi (Make tuzilishni o'rganishi uchun)."""
    publisher = publishers.PUBLISHERS.get(platform)
    if not publisher or not getattr(publisher, "via_webhook", False):
        raise Http404
    try:
        publisher.send_sample()
    except PublishError as exc:
        messages.error(request, f"Namuna yuborilmadi: {exc}")
    else:
        messages.success(request, "Namuna Make.com'ga yuborildi. Make'da ma'lumot tuzilishi aniqlanganini tekshiring.")
    return _back()


@staff_member_required
@require_POST
def connect_remove(request, platform):
    publisher = _oauth_publisher(platform)
    SocialAccount.objects.filter(platform=platform).delete()
    messages.success(request, f"{publisher.label} uzildi.")
    return _back()
