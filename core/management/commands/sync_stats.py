from django.core.management.base import BaseCommand, CommandError

from core import stats_sync


class Command(BaseCommand):
    help = "Instagram/YouTube statistikasini Claude + Composio orqali olib, bazaga yozadi."

    def add_arguments(self, parser):
        parser.add_argument(
            "--if-stale", action="store_true",
            help="Oxirgi yangilanish 20 soatdan eski bo'lsa, faqat shunda ishlaydi (kunlik jadval uchun)",
        )

    def handle(self, *args, **options):
        if options["if_stale"] and not stats_sync.is_stale():
            self.stdout.write("Statistika yangi, o'tkazib yuborildi.")
            return
        try:
            count = stats_sync.sync()
        except stats_sync.StatsError as exc:
            raise CommandError(f"Statistika olinmadi: {exc}")
        self.stdout.write(self.style.SUCCESS(f"{count} ta ko'rsatkich saqlandi."))
