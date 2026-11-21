from django.db import models


class StatSnapshot(models.Model):
    """Ijtimoiy tarmoqdagi bitta ko'rsatkichning bir kunlik qiymati (masalan, Instagram obunachilari)."""

    platform = models.CharField("Platforma", max_length=20)
    metric = models.CharField("Ko'rsatkich", max_length=60)
    value = models.FloatField("Qiymat")
    fetched_at = models.DateTimeField("Olingan vaqt", auto_now_add=True)

    class Meta:
        verbose_name = "Statistika yozuvi"
        verbose_name_plural = "Statistika (kunlik)"
        ordering = ["-fetched_at", "platform", "metric"]
        indexes = [models.Index(fields=["platform", "metric", "-fetched_at"])]

    def __str__(self):
        return f"{self.platform} · {self.metric} = {self.value:g}"
