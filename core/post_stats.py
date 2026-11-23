"""Har bir postning statistikasini yig'adi.

Qoida:
  * faqat Instagram va YouTube (ularda post ID bor va Composio orqali o'qish mumkin);
  * post yuborilganidan keyin 30 kun ichida;
  * 1-haftada kuniga bir marta, keyin haftada bir marta;
  * 30 kundan keyin yangilanmaydi, oxirgi qiymat qoladi.
"""
import json
import logging
import re
from datetime import timedelta

from django.utils import timezone

from . import stats_sync
from .models import PostDelivery
from .stats_models import PostStat

log = logging.getLogger("core.post_stats")

TRACK_DAYS = 30
DAILY_DAYS = 7
PLATFORMS = ("instagram", "youtube")
TOLERANCE = timedelta(hours=1)


def due_targets(now=None):
    """Hozir yangilanishi kerak bo'lgan (delivery) yozuvlari."""
    now = now or timezone.now()
    deliveries = PostDelivery.objects.filter(
        status=PostDelivery.Status.SENT,
        platform__in=PLATFORMS,
        sent_at__gte=now - timedelta(days=TRACK_DAYS),
    ).exclude(external_ids=[])
    targets = []
    for d in deliveries:
        age = now - d.sent_at
        interval = timedelta(days=1) if age <= timedelta(days=DAILY_DAYS) else timedelta(days=7)
        last = PostStat.objects.filter(post_id=d.post_id, platform=d.platform,
                                       external_id=d.external_ids[0]).order_by("-fetched_at").first()
        if last is None or now - last.fetched_at >= interval - TOLERANCE:
            targets.append(d)
    return targets


def build_prompt(targets):
    items = [{"platform": d.platform, "external_id": d.external_ids[0]} for d in targets]
    return (
        "Quyidagi postlarning statistikasini Composio MCP toollari orqali ol. Har biri uchun:\n"
        "- instagram: like_count, comments_count, va video/reel bo'lsa ko'rishlar (plays yoki video_views).\n"
        "- youtube: viewCount, likeCount, commentCount.\n"
        f"Postlar ro'yxati: {json.dumps(items, ensure_ascii=False)}\n\n"
        "Faqat Composio'dan olingan haqiqiy qiymatlarni yoz. Taxmin qilma. Topilmasa, null qo'y.\n"
        "Javobni FAQAT shu JSON shaklida qaytar:\n"
        '{"items": [{"platform": "...", "external_id": "...", "likes": <son|null>, '
        '"comments": <son|null>, "views": <son|null>}]}'
    )


def parse(text, targets):
    """Javobni tekshirib, saqlanadigan qatorlar: [(delivery, metric, value)]."""
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise stats_sync.StatsError("Post statistikasi JSON'i topilmadi.")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise stats_sync.StatsError(f"Post statistikasi JSON'i o'qilmadi: {exc}") from None

    wanted = {(d.platform, d.external_ids[0]): d for d in targets}
    rows = []
    for item in data.get("items") or []:
        if not isinstance(item, dict):
            continue
        key = (str(item.get("platform", "")), str(item.get("external_id", "")))
        delivery = wanted.get(key)
        if not delivery:
            continue  # ro'yxatda yo'q ID'lar e'tiborsiz qoldiriladi
        for metric in ("likes", "comments", "views"):
            value = item.get(metric)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                rows.append((delivery, metric, float(value)))
    return rows


def sync_due(now=None):
    """Navbatdagi postlar statistikasini yangilaydi. Qaytaradi: saqlangan qatorlar soni."""
    targets = due_targets(now)
    if not targets:
        return 0
    text = stats_sync.fetch_raw(build_prompt(targets))
    rows = parse(text, targets)
    PostStat.objects.bulk_create([
        PostStat(post_id=d.post_id, platform=d.platform, external_id=d.external_ids[0], metric=m, value=v)
        for d, m, v in rows
    ])
    log.info("Post statistikasi yangilandi: %s ta ko'rsatkich, %s ta post", len(rows), len(targets))
    return len(rows)
