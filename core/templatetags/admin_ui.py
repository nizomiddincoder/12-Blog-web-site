"""Admin panel dizayni uchun teglar: favicon'lar va bosh sahifa (dashboard) ma'lumotlari."""
import math
from datetime import timedelta

from django import template
from django.db.models import Count
from django.utils import timezone

from ..favicons import favicon_img, favicon_src
from ..models import Company, Post, PostDelivery, Project, SiteSettings

register = template.Library()

PENDING = {"scheduled", "queued", "sending"}
TONES = {
    "sent": "success",
    "failed": "failed",
    "scheduled": "process",
    "queued": "process",
    "sending": "process",
    "skipped": "muted",
    "deleted": "muted",
}
PERIODS = {"week": ("Bu hafta", 7), "month": ("Bu oy", 30), "all": ("Hammasi", None)}


@register.simple_tag
def favicon(target, size=18, css_class=""):
    return favicon_img(target, size, css_class)


@register.simple_tag
def site_settings():
    """SiteSettings — `site` nomi login sahifasida Django tomonidan band qilingani uchun alohida teg."""
    return SiteSettings.load()


@register.simple_tag
def site_favicon(initials):
    """Admin tab uchun favicon: qora fonda bosh harflar (data URI)."""
    letters = "".join(ch for ch in (initials or "?") if ch.isalnum())[:2] or "?"
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>"
        "<rect width='64' height='64' rx='16' fill='%232f2f2f'/>"
        "<text x='32' y='42' text-anchor='middle' font-family='Arial,sans-serif' "
        f"font-size='28' font-weight='700' fill='%23ffffff'>{letters}</text></svg>"
    )
    return "data:image/svg+xml," + svg.replace("<", "%3C").replace(">", "%3E").replace(" ", "%20")


@register.filter
def favicon_url(target):
    return favicon_src(target)


@register.filter
def tone(status):
    return TONES.get(status, "muted")


def post_state(post):
    """Postning umumiy holati: (matn, rang) — jadvaldagi pill uchun."""
    statuses = {d.status for d in post.deliveries.all()}
    if not post.is_published:
        return "Qoralama", "muted"
    if "failed" in statuses:
        return "Xatolik", "failed"
    if statuses & PENDING or post.published_at > timezone.now():
        return "Jarayonda", "process"
    return "Yuborildi" if "sent" in statuses else "Saytda", "success"


def donut(sent, total, radius=70, center=90):
    """Doira diagramma uchun SVG o'lchamlari (yuborilgan ulush)."""
    circumference = 2 * math.pi * radius
    share = sent / total if total else 0
    angle = 2 * math.pi * share - math.pi / 2
    return {
        "r": radius,
        "c": center,
        "circ": round(circumference, 2),
        "sent_len": round(circumference * share, 2),
        "share": round(share * 100),
        # Qiymat yorlig'ining joyi — yuborilgan yoyning oxirida (foizda).
        "tip_x": round((center + radius * math.cos(angle)) / (2 * center) * 100, 1),
        "tip_y": round((center + radius * math.sin(angle)) / (2 * center) * 100, 1),
    }


@register.simple_tag(takes_context=True)
def admin_dashboard(context):
    request = context["request"]
    period = request.GET.get("period", "week")
    if period not in PERIODS:
        period = "week"
    period_label, days = PERIODS[period]
    now = timezone.now()

    deliveries = PostDelivery.objects.select_related("post")
    if days:
        deliveries = deliveries.filter(updated_at__gte=now - timedelta(days=days))
    counts = {
        row["status"]: row["n"]
        for row in deliveries.order_by().values("status").annotate(n=Count("id"))
    }
    total = sum(counts.values())
    sent = counts.get("sent", 0)

    posts = Post.objects.all()
    last_post = posts.order_by("-published_at").first()
    projects = Project.objects.all()
    last_project = projects.order_by("-created_at").first()

    recent_posts = []
    for post in Post.objects.prefetch_related("deliveries", "media")[:5]:
        label, state_tone = post_state(post)
        recent_posts.append({
            "post": post,
            "cover": post.cover,
            "state": label,
            "tone": state_tone,
            "platforms": [d.platform for d in post.deliveries.all()],
        })

    company_sites = list(
        Company.objects.exclude(website="").values_list("website", flat=True)[:3]
    )

    return {
        "period": period,
        "period_label": period_label,
        "periods": [(key, label) for key, (label, _) in PERIODS.items()],
        "posts_total": posts.count(),
        "posts_live": posts.filter(is_published=True, published_at__lte=now).count(),
        "posts_scheduled": posts.filter(is_published=True, published_at__gt=now).count(),
        "last_post": last_post,
        "projects_total": projects.count(),
        "projects_visible": projects.filter(is_visible=True).count(),
        "projects_featured": projects.filter(is_featured=True).count(),
        "last_project": last_project,
        "company_sites": company_sites,
        "deliveries_total": total,
        "deliveries_sent": sent,
        "deliveries_other": total - sent,
        "deliveries_failed": counts.get("failed", 0),
        "donut": donut(sent, total),
        "recent_posts": recent_posts,
        "recent_deliveries": list(deliveries.order_by("-updated_at")[:5]),
    }
