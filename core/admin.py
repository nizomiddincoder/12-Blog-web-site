from django import forms
from django.contrib import admin, messages
from django.db.models import Count, Max
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html, format_html_join

from . import publishers, publishing
from .favicons import favicon_img, host_of
from .media_utils import MEDIA_EXTENSIONS, extension
from .models import (
    FAQ,
    Company,
    Experience,
    Post,
    PostDelivery,
    PostMedia,
    Project,
    ProjectMedia,
    Service,
    SiteSettings,
    SocialAccount,
    Stat,
    Testimonial,
)


# --------------------------------------------------------------------------- #
#  Bir vaqtda bir nechta fayl yuklash maydoni
# --------------------------------------------------------------------------- #
class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault(
            "widget", MultipleFileInput(attrs={"accept": ",".join("." + e for e in MEDIA_EXTENSIONS)})
        )
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single = super().clean
        if isinstance(data, (list, tuple)):
            files = [single(d, initial) for d in data if d]
        else:
            files = [single(data, initial)] if data else []
        bad = [f.name for f in files if extension(f.name) not in MEDIA_EXTENSIONS]
        if bad:
            raise forms.ValidationError(
                "Ruxsat etilmagan fayl turi: %(files)s. Ruxsat etilgan: %(ext)s",
                params={"files": ", ".join(bad), "ext": ", ".join(MEDIA_EXTENSIONS)},
            )
        return files


def media_preview(obj, size=90):
    if not obj or not obj.file:
        return "—"
    url = obj.file.url
    if obj.is_video:
        return format_html(
            '<video src="{}#t=0.1" style="height:{}px;border-radius:6px" muted preload="metadata"></video>', url, size
        )
    return format_html(
        '<a href="{}" target="_blank"><img src="{}" style="height:{}px;border-radius:6px;object-fit:cover"></a>',
        url, url, size,
    )


class MediaInlineBase(admin.TabularInline):
    extra = 0
    fields = ("preview", "file", "caption", "order", "info")
    readonly_fields = ("preview", "info")

    @admin.display(description="Ko'rinish")
    def preview(self, obj):
        return media_preview(obj) if obj and obj.pk else "—"

    @admin.display(description="Ma'lumot")
    def info(self, obj):
        if not obj or not obj.pk:
            return "—"
        parts = [obj.get_kind_display()]
        if obj.width and obj.height:
            parts.append(f"{obj.width}×{obj.height}")
        try:
            parts.append(f"{obj.file.size / 1024 / 1024:.1f} MB")
        except OSError:
            parts.append("fayl topilmadi")
        return " · ".join(parts)


class MediaUploadAdminMixin:
    """Formadagi 'new_media' maydonidan kelgan fayllarni media yozuvlariga aylantiradi."""

    media_model = None
    media_fk = None

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        files = form.cleaned_data.get("new_media") or []
        if files:
            obj = form.instance
            start = obj.media.aggregate(m=Max("order"))["m"] or 0
            for i, f in enumerate(files, start=1):
                self.media_model.objects.create(**{self.media_fk: obj}, file=f, order=start + i)


# --------------------------------------------------------------------------- #
#  Sayt sozlamalari (yagona sahifa)
# --------------------------------------------------------------------------- #
@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Bosh qism (hero)", {"fields": (
            "full_name", "hero_badge", "hero_title", "short_bio", "hero_video", "hero_video_poster",
        )}),
        ("Men haqimda", {"fields": ("avatar", "headline", "about", "location", "resume")}),
        ("Aloqa", {"fields": ("email", "phone")}),
        ("Ijtimoiy tarmoqlar (saytdagi havolalar)", {"fields": (
            "telegram_url", "telegram_channel_url", "instagram_url", "linkedin_url",
            "github_url", "youtube_url", "facebook_url", "x_url",
        )}),
        ("Postlarni yuborish", {"fields": ("telegram_media_mode", "add_site_link")}),
        ("Pastki qism va SEO", {"fields": ("cta_title", "cta_text", "footer_text", "meta_description")}),
    )

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = SiteSettings.load()
        return redirect(reverse("admin:core_sitesettings_change", args=[obj.pk]))


# --------------------------------------------------------------------------- #
#  Oddiy bo'limlar
# --------------------------------------------------------------------------- #
@admin.register(Stat)
class StatAdmin(admin.ModelAdmin):
    list_display = ("value", "label", "order")
    list_editable = ("order",)


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("title", "is_visible", "order")
    list_editable = ("is_visible", "order")


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ("question", "is_visible", "order")
    list_editable = ("is_visible", "order")


@admin.register(Experience)
class ExperienceAdmin(admin.ModelAdmin):
    list_display = ("role", "company", "period", "is_visible", "order")
    list_editable = ("is_visible", "order")


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("logo_preview", "name", "website_link", "is_visible", "order")
    list_display_links = ("logo_preview", "name")
    list_editable = ("is_visible", "order")
    search_fields = ("name",)

    @admin.display(description="Logo")
    def logo_preview(self, obj):
        if obj.logo:
            return format_html('<img src="{}" style="height:36px;max-width:90px;object-fit:contain">', obj.logo.url)
        return favicon_img(obj.website, 28) or "—"

    @admin.display(description="Sayti", ordering="website")
    def website_link(self, obj):
        if not obj.website:
            return "—"
        return format_html(
            '<a class="ds-link-fav" href="{}" target="_blank" rel="noopener">{}{}</a>',
            obj.website, favicon_img(obj.website, 16), host_of(obj.website),
        )


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ("author", "position", "is_visible", "order")
    list_editable = ("is_visible", "order")


# --------------------------------------------------------------------------- #
#  Loyihalar
# --------------------------------------------------------------------------- #
class ProjectMediaInline(MediaInlineBase):
    model = ProjectMedia


class ProjectAdminForm(forms.ModelForm):
    new_media = MultipleFileField(
        label="Galereyaga rasm/video qo'shish", required=False,
        help_text="Bir vaqtda bir nechta fayl tanlash mumkin. Fayllar asl sifatida saqlanadi.",
    )

    class Meta:
        model = Project
        fields = "__all__"


@admin.register(Project)
class ProjectAdmin(MediaUploadAdminMixin, admin.ModelAdmin):
    form = ProjectAdminForm
    media_model = ProjectMedia
    media_fk = "project"
    inlines = [ProjectMediaInline]
    list_display = ("cover_preview", "title", "client", "year", "is_featured", "is_visible", "order")
    list_display_links = ("cover_preview", "title")
    list_editable = ("is_featured", "is_visible", "order")
    search_fields = ("title", "summary", "client", "tags")
    fieldsets = (
        (None, {"fields": ("title", "summary", "description", "cover", "new_media")}),
        ("Ma'lumotlar", {"fields": ("client", "year", "tags", "url")}),
        ("Ko'rinish", {"fields": ("is_featured", "is_visible", "order", "slug")}),
    )

    @admin.display(description="Muqova")
    def cover_preview(self, obj):
        if obj.cover:
            return format_html('<img src="{}" style="height:40px;border-radius:4px">', obj.cover.url)
        return "—"


# --------------------------------------------------------------------------- #
#  Postlar + ijtimoiy tarmoqlar
# --------------------------------------------------------------------------- #
class PostMediaInline(MediaInlineBase):
    model = PostMedia


class PostDeliveryInline(admin.TabularInline):
    model = PostDelivery
    extra = 0
    can_delete = False
    verbose_name_plural = "Platformalardagi holat"
    fields = ("platform_name", "status_badge", "link", "message", "sent_at")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description="Holat")
    def status_badge(self, obj):
        return status_badge(obj)

    @admin.display(description="Havola")
    def link(self, obj):
        if obj.external_url:
            return format_html(
                '<a class="ds-link-fav" href="{}" target="_blank" rel="noopener">{}Ochish</a>',
                obj.external_url, favicon_img(obj.platform, 16),
            )
        return "—"

    @admin.display(description="Platforma")
    def platform_name(self, obj):
        return format_html(
            '<span class="ds-link-fav">{}{}</span>', favicon_img(obj.platform, 18), obj.get_platform_display()
        )


class PostAdminForm(forms.ModelForm):
    new_media = MultipleFileField(
        label="Rasm / video qo'shish", required=False,
        help_text=(
            "Bir vaqtda bir nechta fayl tanlash mumkin (jpg, png, webp, gif, mp4, mov, webm). "
            "Fayllar hech qanday siqilmasdan, asl sifatida saqlanadi."
        ),
    )

    class Meta:
        model = Post
        fields = "__all__"


STATUS_TONES = {
    "scheduled": "process",
    "queued": "process",
    "sending": "process",
    "sent": "success",
    "failed": "failed",
    "skipped": "muted",
    "deleted": "muted",
}


def status_badge(delivery):
    return format_html(
        '<span class="ds-pill ds-pill--{}" title="{}">{}</span>',
        STATUS_TONES.get(delivery.status, "muted"), delivery.message, delivery.get_status_display(),
    )


def platform_chip(delivery):
    """Platforma favicon'i + holat — bitta rangli chip."""
    return format_html(
        '<span class="ds-chip ds-chip--{}" title="{}: {} {}">{}{}</span>',
        STATUS_TONES.get(delivery.status, "muted"), delivery.get_platform_display(),
        delivery.get_status_display(), delivery.message, favicon_img(delivery.platform, 16),
        delivery.get_status_display(),
    )


@admin.register(Post)
class PostAdmin(MediaUploadAdminMixin, admin.ModelAdmin):
    form = PostAdminForm
    media_model = PostMedia
    media_fk = "post"
    inlines = [PostMediaInline, PostDeliveryInline]
    list_display = ("title", "site_state", "published_at", "media_count", "platforms")
    list_filter = ("is_published", "deliveries__platform", "deliveries__status", "published_at")
    search_fields = ("title", "content")
    date_hierarchy = "published_at"
    actions = ["action_send", "action_repost", "action_delete_remote"]
    fieldsets = (
        (None, {"fields": ("title", "content", "new_media")}),
        ("E'lon qilish", {
            "fields": ("is_published", "published_at", ("send_to_telegram", "send_to_linkedin", "send_to_instagram")),
            "description": "Belgilangan va ulangan platformalarga post saqlanganda avtomatik yuboriladi.",
        }),
        ("Qo'shimcha", {"fields": ("slug",), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_media_count=Count("media", distinct=True)) \
            .prefetch_related("deliveries")

    @admin.display(description="Media", ordering="_media_count")
    def media_count(self, obj):
        return obj._media_count

    @admin.display(description="Platformalar")
    def platforms(self, obj):
        deliveries = list(obj.deliveries.all())
        if not deliveries:
            return "—"
        return format_html(
            '<span class="ds-chips">{}</span>',
            format_html_join("", "{}", ((platform_chip(d),) for d in deliveries)),
        )

    @admin.display(description="Saytda", ordering="is_published")
    def site_state(self, obj):
        if not obj.is_published:
            tone, label = "muted", "Qoralama"
        elif not obj.is_live:
            tone, label = "process", "Rejada"
        else:
            tone, label = "success", "E'lon qilingan"
        return format_html('<span class="ds-pill ds-pill--{}">{}</span>', tone, label)

    def render_change_form(self, request, context, *args, **kwargs):
        problems = [f"{p.label}: {p.problem()}" for p in publishers.PUBLISHERS.values() if p.problem()]
        if problems and request.method == "GET":
            self.message_user(
                request,
                "Ulanmagan platformalarga yuborilmaydi — " + "; ".join(problems)
                + ". «Ijtimoiy tarmoqlarni ulash» bo'limiga qarang.",
                messages.INFO,
            )
        return super().render_change_form(request, context, *args, **kwargs)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        queued, scheduled = publishing.sync_after_save(form.instance)
        labels = lambda keys: ", ".join(publishers.get(k).label for k in keys)
        if queued:
            self.message_user(request, f"Post yuborilmoqda: {labels(queued)}. Holatini bir ozdan so'ng ko'ring.")
        if scheduled:
            self.message_user(
                request,
                f"Rejalashtirildi ({labels(scheduled)}): e'lon vaqti kelganda yuboriladi.",
                messages.WARNING,
            )

    @admin.action(description="Yuborilmagan / xato bo'lgan platformalarga yuborish")
    def action_send(self, request, queryset):
        items = [(post.pk, p) for post in queryset for p in publishing.retry_targets(post)]
        publishing.queue(items)
        self.message_user(request, f"{len(items)} ta yuborish navbatga qo'yildi.")

    @admin.action(description="Yangilash: Telegram va LinkedIn'da eskisini o'chirib, qayta joylash")
    def action_repost(self, request, queryset):
        items = [
            (d.post_id, d.platform)
            for d in PostDelivery.objects.filter(post__in=queryset, status=PostDelivery.Status.SENT)
            if publishers.get(d.platform).can_delete
        ]
        publishing.queue(items, repost=True)
        self.message_user(request, f"{len(items)} ta post qayta joylanmoqda. Instagram API o'chirishga ruxsat "
                                   "bermaydi — u yerda qo'lda tahrirlang.")

    @admin.action(description="Telegram va LinkedIn'dan o'chirish (saytda qoladi)")
    def action_delete_remote(self, request, queryset):
        done = 0
        for d in PostDelivery.objects.filter(post__in=queryset, status=PostDelivery.Status.SENT):
            if not publishers.get(d.platform).can_delete:
                continue
            try:
                publishing.delete_remote(d)
                done += 1
            except publishers.PublishError as exc:
                self.message_user(request, f"«{d.post}» ({d.get_platform_display()}): {exc}", messages.ERROR)
        self.message_user(request, f"{done} ta post platformalardan o'chirildi.")


# --------------------------------------------------------------------------- #
#  Ijtimoiy tarmoqlarni ulash
# --------------------------------------------------------------------------- #
@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        from django.template.response import TemplateResponse

        from .connect_views import redirect_uri

        accounts = {a.platform: a for a in SocialAccount.objects.all()}
        rows = []
        for p in publishers.PUBLISHERS.values():
            rows.append({
                "key": p.key,
                "label": p.label,
                "oauth": p.uses_oauth,
                "keys_present": p.keys_present(),
                "account": accounts.get(p.key),
                "problem": p.problem(),
                "redirect_uri": redirect_uri(request, p.key) if p.uses_oauth else "",
            })
        context = {
            **self.admin_site.each_context(request),
            "title": "Ijtimoiy tarmoqlarni ulash",
            "rows": rows,
            "opts": self.model._meta,
        }
        return TemplateResponse(request, "admin/core/connections.html", context)
