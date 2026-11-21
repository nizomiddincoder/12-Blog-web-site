"""Ijtimoiy tarmoqlarga yuboruvchilar. Yangi platforma qo'shish: shu ro'yxatga qo'shiladi."""
from .base import PublishError, Result, Skip  # noqa: F401
from .instagram import InstagramPublisher
from .linkedin import LinkedInPublisher
from .telegram import TelegramPublisher

PUBLISHERS = {p.key: p for p in (TelegramPublisher(), LinkedInPublisher(), InstagramPublisher())}
ORDER = list(PUBLISHERS)


def get(platform):
    return PUBLISHERS[platform]


def ready_platforms():
    return [key for key in ORDER if PUBLISHERS[key].is_ready()]
