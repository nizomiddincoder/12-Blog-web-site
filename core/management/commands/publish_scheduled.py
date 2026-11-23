import logging
import time
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from core import post_stats, publishing, stats_sync

log = logging.getLogger("core.stats")

STATS_RETRY = timedelta(hours=6)  # xato bo'lsa, Claude'ga har daqiqada emas, 6 soatda bir marta uradi
_last_attempt = {}


def _retry_ok(key):
    last = _last_attempt.get(key)
    return not last or timezone.now() - last >= STATS_RETRY


def maybe_sync_stats():
    """Statistikani yangilaydi: kunlik umumiy raqamlar, Telegram va postlar bo'yicha (30 kun)."""
    if settings.TELEGRAM_BOT_TOKEN and stats_sync.is_stale(20, "telegram") and _retry_ok("telegram"):
        _last_attempt["telegram"] = timezone.now()
        try:
            stats_sync.sync_telegram()
        except Exception as exc:  # tarmoq/Telegram xatosi statistikani to'xtatmasin
            log.warning("Telegram obunachilari olinmadi: %s", exc)

    if not (settings.ANTHROPIC_API_KEY and settings.COMPOSIO_API_KEY):
        return
    if stats_sync.is_stale(20) and _retry_ok("daily"):
        _last_attempt["daily"] = timezone.now()
        try:
            count = stats_sync.sync()
            log.info("Kunlik statistika yangilandi: %s ta ko'rsatkich", count)
        except stats_sync.StatsError as exc:
            log.warning("Kunlik statistika olinmadi: %s", exc)

    if post_stats.due_targets() and _retry_ok("posts"):
        _last_attempt["posts"] = timezone.now()
        try:
            post_stats.sync_due()
        except stats_sync.StatsError as exc:
            log.warning("Post statistikasi olinmadi: %s", exc)


class Command(BaseCommand):
    help = (
        "E'lon vaqti kelgan rejalashtirilgan postlarni ijtimoiy tarmoqlarga yuboradi va kunlik "
        "statistikani yangilaydi. Railway'da fon jarayoni sifatida ishlaydi (--loop)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true", help="To'xtovsiz ishlash (har 60 soniyada tekshiradi)")

    def run_once(self):
        for delivery in publishing.run_scheduled():
            self.stdout.write(f"Yuborildi: {delivery.post} → {delivery.get_platform_display()}")
        maybe_sync_stats()

    def handle(self, *args, **options):
        if not options["loop"]:
            self.run_once()
            return
        while True:
            self.run_once()
            time.sleep(60)
