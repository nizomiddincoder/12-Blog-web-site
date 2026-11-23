from django.db import models

PLATFORM_LABELS = {"instagram": "Instagram", "youtube": "YouTube"}
METRIC_LABELS = {
    "followers": "Obunachilar",
    "media_count": "Postlar soni",
    "avg_likes_last5": "Oxirgi 5 ta postda o'rtacha like",
    "avg_comments_last5": "Oxirgi 5 ta postda o'rtacha komment",
    "subscribers": "Obunachilar",
    "views": "Jami ko'rishlar",
    "videos": "Videolar soni",
    "subscribers": "Obunachilar",
}


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

    @property
    def platform_label(self):
        return PLATFORM_LABELS.get(self.platform, self.platform)

    @property
    def metric_label(self):
        return METRIC_LABELS.get(self.metric, self.metric)

    def __str__(self):
        return f"{self.platform_label} · {self.metric_label} = {self.value:g}"


class PostStat(models.Model):
    """Bitta postning bitta platformadagi ko'rsatkichi (like, komment, ko'rishlar)."""

    post = models.ForeignKey("core.Post", on_delete=models.CASCADE, related_name="stats")
    platform = models.CharField("Platforma", max_length=20)
    external_id = models.CharField("Tashqi ID", max_length=200)
    metric = models.CharField("Ko'rsatkich", max_length=40)
    value = models.FloatField("Qiymat")
    fetched_at = models.DateTimeField("Olingan vaqt", auto_now_add=True)

    class Meta:
        verbose_name = "Post statistikasi"
        verbose_name_plural = "Postlar statistikasi"
        ordering = ["-fetched_at"]
        indexes = [models.Index(fields=["post", "platform", "-fetched_at"])]

    POST_METRIC_LABELS = {"likes": "Like", "comments": "Komment", "views": "Ko'rishlar"}

    @property
    def metric_label(self):
        return self.POST_METRIC_LABELS.get(self.metric, self.metric)

    def __str__(self):
        return f"{self.post} · {self.platform} · {self.metric_label} = {self.value:g}"
