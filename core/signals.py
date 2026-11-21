"""Yozuv o'chirilganda yoki fayl almashtirilganda eski faylni diskdan ham o'chiradi."""
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from .models import Company, PostMedia, Project, ProjectMedia, SiteSettings, Testimonial

FILE_FIELDS = {
    PostMedia: ["file"],
    ProjectMedia: ["file"],
    Project: ["cover"],
    Company: ["logo"],
    Testimonial: ["photo"],
    SiteSettings: ["avatar", "resume", "hero_video", "hero_video_poster"],
}


def _delete_file(field_file):
    if field_file and field_file.name:
        try:
            field_file.storage.delete(field_file.name)
        except Exception:
            pass


def _on_delete(sender, instance, **kwargs):
    for name in FILE_FIELDS[sender]:
        _delete_file(getattr(instance, name))
    if sender is PostMedia:  # Instagram uchun yasalgan JPEG nusxalar
        storage = instance.file.storage
        try:
            _, files = storage.listdir("instagram")
        except (FileNotFoundError, NotImplementedError, OSError):
            return
        for name in files:
            if name.startswith(f"{instance.pk}-"):
                storage.delete(f"instagram/{name}")


def _on_replace(sender, instance, **kwargs):
    if not instance.pk:
        return
    old = sender.objects.filter(pk=instance.pk).first()
    if not old:
        return
    for name in FILE_FIELDS[sender]:
        old_file, new_file = getattr(old, name), getattr(instance, name)
        if old_file and old_file.name != (new_file.name if new_file else None):
            _delete_file(old_file)


for _model in FILE_FIELDS:
    receiver(post_delete, sender=_model, dispatch_uid=f"del-{_model.__name__}")(_on_delete)
    receiver(pre_save, sender=_model, dispatch_uid=f"rep-{_model.__name__}")(_on_replace)
