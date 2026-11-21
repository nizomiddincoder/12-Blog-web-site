import logging
import time
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from core import publishing, stats_sync

log = logging.getLogger("core.stats")

STATS_RETRY = timedelta(hours=6)  # xato bo'lsa, Claude'ga har daqiqada emas, 6 soatda bir marta uradi
_last_stats_attempt = None


def maybe_sync_stats():
    """Statistika 20 soatdan eski bo'lsa yangilaydi. Muvaffaqiyatsizlikda tez-tez qayta urinmaydi."""
    global _last_stats_attempt
    if not (settings.ANTHROPIC_API_KEY and settings.COMPOSIO_API_KEY):
        return
    if not stats_sync.is_stale():
        return
    if _last_stats_attempt and timezone.now() - _last_stats_attempt < STATS_RETRY:
        return
    _last_stats_attempt = timezone.now()
    try:
        count = stats_sync.sync()
        log.info("Kunlik statistika yangilandi: %s ta ko'rsatkich", count)
    except stats_sync.StatsError as exc:
        log.warning("Kunlik statistika olinmadi: %s", exc)


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
