from django.core.management.base import BaseCommand, CommandError

from core.publishers import PublishError
from core.publishers.telegram import check_connection


class Command(BaseCommand):
    help = "Telegram bot va kanal sozlamalarini tekshiradi."

    def handle(self, *args, **options):
        try:
            for line in check_connection():
                self.stdout.write(line)
        except PublishError as exc:
            raise CommandError(f"Xatolik: {exc}")
