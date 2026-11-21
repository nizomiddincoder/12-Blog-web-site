import time

from django.core.management.base import BaseCommand

from core import publishing


class Command(BaseCommand):
    help = (
        "E'lon vaqti kelgan rejalashtirilgan postlarni ijtimoiy tarmoqlarga yuboradi. "
        "Cron orqali har daqiqada ishga tushiring yoki --loop bilan doimiy ishlating."
    )

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true", help="To'xtovsiz ishlash (har 60 soniyada tekshiradi)")

    def run_once(self):
        for delivery in publishing.run_scheduled():
            self.stdout.write(f"Yuborildi: {delivery.post} → {delivery.get_platform_display()}")

    def handle(self, *args, **options):
        if not options["loop"]:
            self.run_once()
            return
        while True:
            self.run_once()
            time.sleep(60)
