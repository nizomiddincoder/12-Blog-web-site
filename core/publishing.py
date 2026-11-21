"""Postlarni platformalarga yuborishni boshqaradi: navbat, fon oqimi, holatlarni yozish."""
import logging
import threading

from django.db import close_old_connections, connections, transaction
from django.utils import timezone

from . import publishers
from .models import Post, PostDelivery
from .publishers import PublishError, Skip

log = logging.getLogger("core.publishing")
Status = PostDelivery.Status


def sync_after_save(post):
    """Admin saqlagandan keyin: qaysi platformalarga yuborish kerakligini aniqlaydi va navbatga qo'yadi.

    Faqat hali yuborilmagan platformalarga yuboriladi — tahrirlash postni qayta yubormaydi.
    Qaytaradi: (navbatga qo'yilganlar, rejalashtirilganlar).
    """
    ready = set(publishers.ready_platforms())
    existing = {d.platform: d for d in post.deliveries.all()}
    to_queue, scheduled = [], []
    for platform in publishers.ORDER:
        delivery = existing.get(platform)
        wanted = post.is_published and post.wants(platform) and platform in ready
        if delivery and delivery.status == Status.SCHEDULED and not wanted:
            delivery.delete()
            continue
        if not wanted:
            continue
        if delivery is None:
            if post.is_live:
                to_queue.append(platform)
            else:
                PostDelivery.objects.create(post=post, platform=platform, status=Status.SCHEDULED)
                scheduled.append(platform)
        elif delivery.status == Status.SCHEDULED:
            (to_queue if post.is_live else scheduled).append(platform)
    queue([(post.pk, p) for p in to_queue])
    return to_queue, scheduled


def retry_targets(post):
    """'Yuborish' amali uchun: belgilangan, tayyor va hali yuborilmagan/xato bo'lgan platformalar."""
    if not post.is_live:
        return []
    ready = set(publishers.ready_platforms())
    existing = {d.platform: d.status for d in post.deliveries.all()}
    return [
        p for p in publishers.ORDER
        if post.wants(p) and p in ready
        and existing.get(p) in (None, Status.FAILED, Status.DELETED, Status.SCHEDULED, Status.QUEUED)
    ]


def queue(items, repost=False):
    """items: [(post_id, platform), ...]. Fon oqimida navbat bilan yuboradi."""
    items = list(items)
    if not items:
        return
    for post_id, platform in items:
        delivery, created = PostDelivery.objects.get_or_create(
            post_id=post_id, platform=platform, defaults={"status": Status.QUEUED}
        )
        if not created and delivery.status != Status.SENDING:
            PostDelivery.objects.filter(pk=delivery.pk).update(status=Status.QUEUED, message="")
    transaction.on_commit(lambda: threading.Thread(target=_worker, args=(items, repost), daemon=True).start())


def _worker(items, repost):
    close_old_connections()
    try:
        for post_id, platform in items:
            run(post_id, platform, repost=repost)
    finally:
        connections.close_all()


def run(post_id, platform, repost=False):
    """Bitta postni bitta platformaga sinxron yuboradi va natijani yozadi."""
    locked = PostDelivery.objects.filter(post_id=post_id, platform=platform).exclude(
        status=Status.SENDING
    ).update(status=Status.SENDING, message="")
    if not locked:
        return
    delivery = PostDelivery.objects.get(post_id=post_id, platform=platform)
    post = Post.objects.prefetch_related("media").get(pk=post_id)
    publisher = publishers.get(platform)
    try:
        if repost and delivery.external_ids and publisher.can_delete:
            try:
                publisher.delete(delivery)
            except PublishError as exc:
                log.warning("%s: eski postni o'chirib bo'lmadi: %s", platform, exc)
        result = publisher.publish(post)
    except Skip as exc:
        PostDelivery.objects.filter(pk=delivery.pk).update(status=Status.SKIPPED, message=str(exc))
        return
    except Exception as exc:
        if isinstance(exc, PublishError):
            log.warning("Post %s → %s: %s", post_id, platform, exc)
        else:
            log.exception("Post %s → %s yuborilmadi", post_id, platform)
        PostDelivery.objects.filter(pk=delivery.pk).update(
            status=Status.FAILED, message=str(exc) or exc.__class__.__name__
        )
        return
    PostDelivery.objects.filter(pk=delivery.pk).update(
        status=Status.SENT, external_ids=result.ids, external_url=result.url,
        message="\n".join(result.warnings), sent_at=timezone.now(),
    )
    log.info("Post %s → %s yuborildi", post_id, platform)


def delete_remote(delivery):
    publisher = publishers.get(delivery.platform)
    publisher.delete(delivery)
    PostDelivery.objects.filter(pk=delivery.pk).update(
        status=Status.DELETED, external_ids=[], external_url="", message=""
    )


def run_scheduled():
    """Vaqti kelgan rejalashtirilgan yuborishlarni bajaradi (publish_scheduled buyrug'i)."""
    due = PostDelivery.objects.filter(
        status=Status.SCHEDULED, post__is_published=True, post__published_at__lte=timezone.now()
    ).order_by("post__published_at")
    done = []
    for delivery in due:
        PostDelivery.objects.filter(pk=delivery.pk).update(status=Status.QUEUED)
        run(delivery.post_id, delivery.platform)
        done.append(delivery)
    return done
