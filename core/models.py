import os

from django.core.validators import FileExtensionValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from .media_utils import (
    MEDIA_EXTENSIONS,
    detect_kind,
    probe_image,
    probe_video,
    unique_slug,
)


# --------------------------------------------------------------------------- #
#  Sayt sozlamalari (yagona yozuv)
# --------------------------------------------------------------------------- #
class SiteSettings(models.Model):
    class TelegramMediaMode(models.TextChoices):
        ORIGINAL = "original", "Asl sifatda (rasmlar fayl sifatida yuboriladi)"
        COMPRESSED = "compressed", "Oddiy rasm (Telegram rasmni siqadi)"

    # Asosiy
    full_name = models.CharField("Ism familiya", max_length=120, default="Ism Familiya")
    headline = models.CharField(
        "Kasbingiz / qisqa sarlavha", max_length=160, blank=True,
        help_text="Masalan: Full-stack dasturchi, tadbirkor",
    )
    hero_badge = models.CharField(
        "Yuqoridagi kichik yozuv", max_length=120, blank=True,
        help_text="Masalan: Yangi loyihalar uchun ochiqman",
    )
    hero_title = models.CharField(
        "Bosh sarlavha", max_length=200, blank=True,
        help_text="Bosh sahifadagi katta sarlavha. Bo'sh bo'lsa ismingiz chiqadi.",
    )
    short_bio = models.TextField("Qisqa tanishtiruv", blank=True, help_text="Bosh sarlavha ostidagi 1–2 qator matn")
    hero_video = models.FileField(
        "Bosh sahifa videosi (16:9)", upload_to="site/", blank=True,
        validators=[FileExtensionValidator(["mp4", "webm", "mov", "m4v"])],
        help_text="Ixtiyoriy. Sarlavha ostida chiqadi. Asl sifatida ko'rsatiladi.",
    )
    hero_video_poster = models.ImageField("Video muqovasi", upload_to="site/", blank=True)
    avatar = models.ImageField("Rasmingiz (portret)", upload_to="site/", blank=True)

    # Men haqimda
    about = models.TextField("Men haqimda (batafsil)", blank=True)
    location = models.CharField("Joylashuv", max_length=120, blank=True)
    resume = models.FileField("Rezyume (CV) fayli", upload_to="site/", blank=True)

    # Aloqa
    email = models.EmailField("Email", blank=True)
    phone = models.CharField("Telefon", max_length=40, blank=True)

    # Ijtimoiy tarmoqlar
    telegram_url = models.URLField("Telegram (shaxsiy)", blank=True)
    telegram_channel_url = models.URLField("Telegram kanal havolasi", blank=True)
    instagram_url = models.URLField("Instagram", blank=True)
    linkedin_url = models.URLField("LinkedIn", blank=True)
    github_url = models.URLField("GitHub", blank=True)
    youtube_url = models.URLField("YouTube", blank=True)
    facebook_url = models.URLField("Facebook", blank=True)
    x_url = models.URLField("X (Twitter)", blank=True)

    # Telegram
    telegram_media_mode = models.CharField(
        "Telegramga rasm yuborish usuli", max_length=20,
        choices=TelegramMediaMode.choices, default=TelegramMediaMode.ORIGINAL,
        help_text=(
            "Telegram 'rasm' sifatida yuborilgan suratlarni doim siqadi. Asl sifat kerak bo'lsa — "
            "'Asl sifatda' tanlang (rasm fayl ko'rinishida chiqadi). Videolar har ikki holatda ham siqilmaydi."
        ),
    )
    add_site_link = models.BooleanField(
        "Ijtimoiy tarmoqdagi postlarga saytdagi havolani qo'shish", default=True,
        help_text="Faqat SITE_URL ko'rsatilgan bo'lsa ishlaydi (Railway'da avtomatik)",
    )

    # Yakuniy chaqiriq
    cta_title = models.CharField("Pastdagi chaqiriq sarlavhasi", max_length=160, default="Birga ishlaymizmi?")
    cta_text = models.CharField(
        "Pastdagi chaqiriq matni", max_length=300, blank=True,
        default="Loyihangiz yoki taklifingiz bo'lsa — yozing, albatta javob beraman.",
    )

    # SEO / footer
    meta_description = models.CharField("Sayt tavsifi (SEO)", max_length=300, blank=True)
    footer_text = models.CharField("Pastki qismdagi yozuv", max_length=200, blank=True)

    class Meta:
        verbose_name = "Sayt sozlamalari"
        verbose_name_plural = "Sayt sozlamalari"

    def __str__(self):
        return "Sayt sozlamalari"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def social_links(self):
        items = [
            ("Telegram", self.telegram_url, "bi-telegram"),
            ("Instagram", self.instagram_url, "bi-instagram"),
            ("LinkedIn", self.linkedin_url, "bi-linkedin"),
            ("GitHub", self.github_url, "bi-github"),
            ("YouTube", self.youtube_url, "bi-youtube"),
            ("Facebook", self.facebook_url, "bi-facebook"),
            ("X", self.x_url, "bi-twitter-x"),
        ]
        return [{"name": n, "url": u, "icon": i} for n, u, i in items if u]

    @property
    def initials(self):
        parts = [p for p in self.full_name.split() if p]
        return "".join(p[0] for p in parts[:2]).upper() or "?"


# --------------------------------------------------------------------------- #
#  "Men kimman" bo'limlari
# --------------------------------------------------------------------------- #
class OrderedModel(models.Model):
    order = models.PositiveIntegerField("Tartib", default=0, help_text="Kichik raqam oldinda chiqadi")

    class Meta:
        abstract = True
        ordering = ["order", "id"]


class VisibleQuerySet(models.QuerySet):
    def visible(self):
        return self.filter(is_visible=True)


class Stat(OrderedModel):
    value = models.CharField("Qiymat", max_length=30, help_text="Masalan: 5+ yoki 120")
    label = models.CharField("Izoh", max_length=80, help_text="Masalan: yillik tajriba")

    class Meta(OrderedModel.Meta):
        verbose_name = "Raqam (statistika)"
        verbose_name_plural = "Raqamlar (statistika)"

    def __str__(self):
        return f"{self.value} — {self.label}"


class FAQ(OrderedModel):
    question = models.CharField("Savol", max_length=255)
    answer = models.TextField("Javob")
    is_visible = models.BooleanField("Ko'rinsin", default=True)

    objects = VisibleQuerySet.as_manager()

    class Meta(OrderedModel.Meta):
        verbose_name = "Savol-javob"
        verbose_name_plural = "Savol-javoblar (FAQ)"

    def __str__(self):
        return self.question


class Service(OrderedModel):
    title = models.CharField("Nomi", max_length=120)
    description = models.TextField("Tavsif", blank=True)
    is_visible = models.BooleanField("Ko'rinsin", default=True)

    objects = VisibleQuerySet.as_manager()

    class Meta(OrderedModel.Meta):
        verbose_name = "Xizmat / yo'nalish"
        verbose_name_plural = "Xizmatlar / yo'nalishlar"

    def __str__(self):
        return self.title


class Experience(OrderedModel):
    role = models.CharField("Lavozim", max_length=120)
    company = models.CharField("Kompaniya", max_length=120)
    period = models.CharField("Davr", max_length=60, help_text="Masalan: 2021 — hozir")
    description = models.TextField("Tavsif", blank=True)
    is_visible = models.BooleanField("Ko'rinsin", default=True)

    objects = VisibleQuerySet.as_manager()

    class Meta(OrderedModel.Meta):
        verbose_name = "Tajriba"
        verbose_name_plural = "Tajriba (ish joylari)"

    def __str__(self):
        return f"{self.role} — {self.company}"


class Company(OrderedModel):
    name = models.CharField("Nomi", max_length=120)
    logo = models.ImageField("Logotip", upload_to="companies/", blank=True, help_text="Shaffof fonli PNG yoki WEBP tavsiya etiladi")
    website = models.URLField("Sayti", blank=True)
    description = models.CharField("Qisqa izoh", max_length=200, blank=True)
    is_visible = models.BooleanField("Ko'rinsin", default=True)

    objects = VisibleQuerySet.as_manager()

    class Meta(OrderedModel.Meta):
        verbose_name = "Kompaniya (hamkor)"
        verbose_name_plural = "Men bilan ishlagan kompaniyalar"

    def __str__(self):
        return self.name


class Testimonial(OrderedModel):
    author = models.CharField("Muallif", max_length=120)
    position = models.CharField("Lavozimi / kompaniyasi", max_length=160, blank=True)
    text = models.TextField("Fikr")
    photo = models.ImageField("Rasm", upload_to="testimonials/", blank=True)
    is_visible = models.BooleanField("Ko'rinsin", default=True)

    objects = VisibleQuerySet.as_manager()

    class Meta(OrderedModel.Meta):
        verbose_name = "Fikr-mulohaza"
        verbose_name_plural = "Fikr-mulohazalar"

    def __str__(self):
        return self.author


# --------------------------------------------------------------------------- #
#  Media (rasm/video) — asl holida saqlanadi
# --------------------------------------------------------------------------- #
def media_upload_to(instance, filename):
    return f"{instance.UPLOAD_DIR}/{timezone.now():%Y/%m}/{filename}"


class MediaBase(models.Model):
    UPLOAD_DIR = "media"

    class Kind(models.TextChoices):
        IMAGE = "image", "Rasm"
        VIDEO = "video", "Video"
        FILE = "file", "Fayl"

    file = models.FileField(
        "Fayl (rasm yoki video)", upload_to=media_upload_to, max_length=255,
        validators=[FileExtensionValidator(MEDIA_EXTENSIONS)],
    )
    kind = models.CharField("Turi", max_length=10, choices=Kind.choices, editable=False, default=Kind.IMAGE)
    caption = models.CharField("Izoh", max_length=255, blank=True)
    width = models.PositiveIntegerField(null=True, blank=True, editable=False)
    height = models.PositiveIntegerField(null=True, blank=True, editable=False)
    duration = models.FloatField(null=True, blank=True, editable=False)
    order = models.PositiveIntegerField("Tartib", default=0)

    class Meta:
        abstract = True
        ordering = ["order", "id"]

    def __str__(self):
        return os.path.basename(self.file.name)

    @property
    def is_video(self):
        return self.kind == self.Kind.VIDEO

    @property
    def is_image(self):
        return self.kind == self.Kind.IMAGE

    @property
    def filename(self):
        return os.path.basename(self.file.name)

    def save(self, *args, **kwargs):
        self.kind = detect_kind(self.file.name)
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).values_list("file", flat=True).first()
            if old != self.file.name:
                self.width = self.height = self.duration = None
        super().save(*args, **kwargs)
        if self.width is None and self.file:
            self._probe()

    def _probe(self):
        try:
            path = self.file.path
        except NotImplementedError:
            return
        if self.kind == self.Kind.IMAGE:
            w, h, d = probe_image(path)
        elif self.kind == self.Kind.VIDEO:
            w, h, d = probe_video(path)
        else:
            return
        if w or h or d:
            self.width, self.height, self.duration = w, h, d
            type(self).objects.filter(pk=self.pk).update(width=w, height=h, duration=d)


# --------------------------------------------------------------------------- #
#  Loyihalar (qilgan ishlarim)
# --------------------------------------------------------------------------- #
class Project(OrderedModel):
    title = models.CharField("Nomi", max_length=200)
    slug = models.SlugField("Havola (slug)", max_length=100, unique=True, blank=True, help_text="Bo'sh qoldirsangiz avtomatik yaratiladi")
    summary = models.CharField("Qisqa tavsif", max_length=300, blank=True)
    description = models.TextField("Batafsil", blank=True)
    cover = models.ImageField("Muqova rasmi", upload_to="projects/covers/", blank=True)
    client = models.CharField("Mijoz / kompaniya", max_length=120, blank=True)
    year = models.CharField("Yil", max_length=20, blank=True)
    tags = models.CharField("Teglar", max_length=200, blank=True, help_text="Vergul bilan: Django, Dizayn, SMM")
    url = models.URLField("Havola (loyiha sayti)", blank=True)
    is_featured = models.BooleanField("Bosh sahifada ko'rsatish", default=True)
    is_visible = models.BooleanField("Ko'rinsin", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = VisibleQuerySet.as_manager()

    class Meta(OrderedModel.Meta):
        verbose_name = "Loyiha (qilgan ishim)"
        verbose_name_plural = "Loyihalar (qilgan ishlarim)"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.title, "loyiha")
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("project_detail", args=[self.slug])

    @property
    def tag_list(self):
        return [t.strip() for t in self.tags.split(",") if t.strip()]


class ProjectMedia(MediaBase):
    UPLOAD_DIR = "projects"
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="media")

    class Meta(MediaBase.Meta):
        verbose_name = "Loyiha rasmi/videosi"
        verbose_name_plural = "Loyiha rasmlari/videolari"


# --------------------------------------------------------------------------- #
#  Blog postlari (yangiliklar)
# --------------------------------------------------------------------------- #
class PostQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_published=True, published_at__lte=timezone.now())


class Platform(models.TextChoices):
    TELEGRAM = "telegram", "Telegram"
    LINKEDIN = "linkedin", "LinkedIn"
    INSTAGRAM = "instagram", "Instagram"


class Post(models.Model):
    title = models.CharField("Sarlavha", max_length=255)
    slug = models.SlugField("Havola (slug)", max_length=100, unique=True, blank=True, help_text="Bo'sh qoldirsangiz avtomatik yaratiladi")
    content = models.TextField("Matn", blank=True)

    is_published = models.BooleanField("Saytda e'lon qilish", default=True)
    published_at = models.DateTimeField(
        "E'lon vaqti", default=timezone.now,
        help_text="Kelajakdagi vaqt qo'ysangiz, post o'sha vaqtda chiqadi (README: rejalashtirilgan postlar)",
    )
    send_to_telegram = models.BooleanField("Telegram kanalga", default=True)
    send_to_linkedin = models.BooleanField("LinkedIn'ga", default=True)
    send_to_instagram = models.BooleanField(
        "Instagram'ga", default=True, help_text="Instagram faqat rasm yoki videoli postlarni qabul qiladi",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PostQuerySet.as_manager()

    class Meta:
        ordering = ["-published_at", "-id"]
        verbose_name = "Post (yangilik)"
        verbose_name_plural = "Postlar (yangiliklar)"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.title, "post")
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("post_detail", args=[self.slug])

    @property
    def is_live(self):
        return self.is_published and self.published_at <= timezone.now()

    @property
    def cover(self):
        items = list(self.media.all())
        return items[0] if items else None

    def wants(self, platform):
        return bool(getattr(self, f"send_to_{platform}", False))


class PostMedia(MediaBase):
    UPLOAD_DIR = "posts"
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="media")

    class Meta(MediaBase.Meta):
        verbose_name = "Post rasmi/videosi"
        verbose_name_plural = "Post rasmlari/videolari"


class PostDelivery(models.Model):
    """Postning bitta platformaga yuborilish holati."""

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Rejalashtirilgan"
        QUEUED = "queued", "Navbatda"
        SENDING = "sending", "Yuborilmoqda"
        SENT = "sent", "Yuborildi"
        FAILED = "failed", "Xatolik"
        SKIPPED = "skipped", "O'tkazib yuborildi"
        DELETED = "deleted", "O'chirilgan"

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="deliveries")
    platform = models.CharField("Platforma", max_length=20, choices=Platform.choices)
    status = models.CharField("Holat", max_length=20, choices=Status.choices, default=Status.QUEUED)
    external_ids = models.JSONField("Tashqi ID lar", default=list, blank=True)
    external_url = models.URLField("Postga havola", max_length=500, blank=True)
    message = models.TextField("Xato / ogohlantirish", blank=True)
    sent_at = models.DateTimeField("Yuborilgan vaqt", null=True, blank=True)
    updated_at = models.DateTimeField("Yangilangan", auto_now=True)

    class Meta:
        verbose_name = "Platformaga yuborish"
        verbose_name_plural = "Platformalarga yuborish"
        ordering = ["platform"]
        constraints = [models.UniqueConstraint(fields=["post", "platform"], name="unique_post_platform")]

    def __str__(self):
        return f"{self.get_platform_display()}: {self.get_status_display()}"


class SocialAccount(models.Model):
    """OAuth orqali ulangan akkaunt (LinkedIn, Instagram). Tokenlar shu yerda saqlanadi."""

    platform = models.CharField("Platforma", max_length=20, choices=Platform.choices, unique=True)
    account_id = models.CharField("Akkaunt ID", max_length=120)
    account_name = models.CharField("Akkaunt nomi", max_length=200, blank=True)
    access_token = models.TextField()
    refresh_token = models.TextField(blank=True)
    expires_at = models.DateTimeField("Ulanish muddati", null=True, blank=True)
    connected_at = models.DateTimeField("Ulangan vaqt", default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ulangan akkaunt"
        verbose_name_plural = "Ijtimoiy tarmoqlarni ulash"

    def __str__(self):
        return f"{self.get_platform_display()} — {self.account_name or self.account_id}"

    @property
    def is_expired(self):
        return bool(self.expires_at and self.expires_at <= timezone.now())

    @property
    def days_left(self):
        if not self.expires_at:
            return None
        return max((self.expires_at - timezone.now()).days, 0)
