"""Instagram/YouTube statistikasini Claude API orqali (Composio MCP ulanishi bilan) olib, bazaga yozadi.

Oqim: Claude API → mcp_servers (Composio MCP) → Claude toollarni chaqiradi → JSON qaytaradi
→ biz JSON'ni tekshiramiz → StatSnapshot ga yozamiz.

Claude hech qachon bazaga to'g'ridan-to'g'ri yozmaydi. Qiymatlar faqat JSON'dan olinadi.
"""
import json
import logging
import re
from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone

from .stats_models import StatSnapshot

log = logging.getLogger("core.stats")

API_URL = "https://api.anthropic.com/v1/messages"
SERVER_NAME = "composio"

PROMPT = """Composio MCP orqali ulangan akkauntlar statistikasini ol.

1. Instagram (Business akkaunt): followers_count, media_count va oxirgi 5 ta postning like va comment soni.
2. YouTube: agar ulangan bo'lsa — subscriberCount, viewCount, videoCount. Ulanmagan bo'lsa, null qaytar.

Faqat Composio toollaridan olingan haqiqiy qiymatlarni yoz. Taxmin qilma. Xato bo'lsa, errors ro'yxatiga yoz.

Javobni FAQAT quyidagi JSON shaklida qaytar, boshqa matn qo'shma:
{"instagram": {"followers": <son yoki null>, "media_count": <son yoki null>,
   "recent_posts": [{"likes": <son>, "comments": <son>}]},
 "youtube": {"subscribers": <son yoki null>, "views": <son yoki null>, "videos": <son yoki null>} yoki null,
 "errors": ["..."]}
"""


class StatsError(Exception):
    pass


def _extract_json(text):
    """Javob matnidan birinchi JSON obyektini ajratadi."""
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise StatsError("Claude javobida JSON topilmadi.")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise StatsError(f"JSON o'qilmadi: {exc}") from None


def _num(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_request(prompt=PROMPT):
    if not settings.ANTHROPIC_API_KEY:
        raise StatsError("ANTHROPIC_API_KEY ko'rsatilmagan.")
    if not settings.COMPOSIO_API_KEY:
        raise StatsError("COMPOSIO_API_KEY ko'rsatilmagan.")
    headers = {
        "x-api-key": settings.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "anthropic-beta": settings.ANTHROPIC_MCP_BETA,
        "content-type": "application/json",
    }
    body = {
        "model": settings.ANTHROPIC_MODEL,
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": prompt}],
        "mcp_servers": [{
            "type": "url",
            "url": settings.COMPOSIO_MCP_URL,
            "name": SERVER_NAME,
            "authorization_token": settings.COMPOSIO_API_KEY,
        }],
        "tools": [{"type": "mcp_toolset", "mcp_server_name": SERVER_NAME}],
    }
    return headers, body


def fetch_raw(prompt=PROMPT):
    """Claude API'ga so'rov yuboradi va matnli javobni qaytaradi."""
    headers, body = build_request(prompt)
    try:
        resp = requests.post(API_URL, headers=headers, json=body, timeout=(20, 300))
    except requests.RequestException as exc:
        raise StatsError(f"Claude API bilan aloqa yo'q: {exc}") from None
    if resp.status_code >= 400:
        raise StatsError(f"Claude API HTTP {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    text = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
    if not text.strip():
        raise StatsError("Claude bo'sh javob qaytardi.")
    return text


def parse(text):
    """Qaytgan JSON'ni tekshirib, saqlanadigan qatorlar ro'yxatini tuzadi: [(platform, metric, value)]."""
    data = _extract_json(text)
    rows = []

    ig = data.get("instagram") or {}
    for metric, key in (("followers", "followers"), ("media_count", "media_count")):
        value = _num(ig.get(key))
        if value is not None:
            rows.append(("instagram", metric, value))
    posts = [p for p in (ig.get("recent_posts") or []) if isinstance(p, dict)][:5]
    if posts:
        likes = [_num(p.get("likes")) for p in posts]
        comments = [_num(p.get("comments")) for p in posts]
        likes = [v for v in likes if v is not None]
        comments = [v for v in comments if v is not None]
        if likes:
            rows.append(("instagram", "avg_likes_last5", sum(likes) / len(likes)))
        if comments:
            rows.append(("instagram", "avg_comments_last5", sum(comments) / len(comments)))

    yt = data.get("youtube") or {}
    if isinstance(yt, dict):
        for metric, key in (("subscribers", "subscribers"), ("views", "views"), ("videos", "videos")):
            value = _num(yt.get(key))
            if value is not None:
                rows.append(("youtube", metric, value))

    return rows


def sync():
    """Bir marta statistikani oladi va saqlaydi. Qaytaradi: saqlangan qatorlar soni."""
    text = fetch_raw()
    rows = parse(text)
    if not rows:
        raise StatsError("Hech qanday ko'rsatkich olinmadi. Composio ulanishini tekshiring.")
    StatSnapshot.objects.bulk_create([
        StatSnapshot(platform=p, metric=m, value=v) for p, m, v in rows
    ])
    log.info("Statistika yangilandi: %s ta ko'rsatkich", len(rows))
    return len(rows)


def sync_telegram():
    """Telegram kanal obunachilari sonini (Bot API orqali, Composio'siz) saqlaydi."""
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHANNEL_ID:
        return 0
    from .publishers.telegram import call

    count = call("getChatMemberCount", data={"chat_id": settings.TELEGRAM_CHANNEL_ID})
    StatSnapshot.objects.create(platform="telegram", metric="subscribers", value=float(count))
    return 1


def is_stale(hours=20, platform=None):
    """Oxirgi yangilanish shu vaqtdan eski bo'lsa True."""
    qs = StatSnapshot.objects.all()
    if platform:
        qs = qs.filter(platform=platform)
    last = qs.order_by("-fetched_at").first()
    return not last or last.fetched_at < timezone.now() - timedelta(hours=hours)
