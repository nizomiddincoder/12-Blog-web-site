from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from .models import FAQ, Company, Experience, Post, Project, Service, Stat, Testimonial


def home(request):
    context = {
        "stats": Stat.objects.all(),
        "services": Service.objects.visible(),
        "experiences": Experience.objects.visible(),
        "companies": Company.objects.visible(),
        "projects": Project.objects.visible().filter(is_featured=True).prefetch_related("media")[:6],
        "projects_total": Project.objects.visible().count(),
        "testimonials": Testimonial.objects.visible(),
        "posts": Post.objects.published().prefetch_related("media")[:3],
        "faqs": FAQ.objects.visible(),
    }
    return render(request, "home.html", context)


def privacy(request):
    return render(request, "privacy.html")


def post_list(request):
    posts = Post.objects.published().prefetch_related("media")
    query = request.GET.get("q", "").strip()
    if query:
        posts = posts.filter(Q(title__icontains=query) | Q(content__icontains=query))
    page = Paginator(posts, 9).get_page(request.GET.get("page"))
    return render(request, "blog/post_list.html", {"page": page, "query": query})


def post_detail(request, slug):
    base = Post.objects.all() if request.user.is_staff else Post.objects.published()
    post = get_object_or_404(base.prefetch_related("media"), slug=slug)
    published = Post.objects.published()
    context = {
        "post": post,
        "media": list(post.media.all()),
        "newer": published.filter(published_at__gt=post.published_at).order_by("published_at").first(),
        "older": published.filter(published_at__lt=post.published_at).order_by("-published_at").first(),
    }
    return render(request, "blog/post_detail.html", context)


def project_list(request):
    projects = Project.objects.visible().prefetch_related("media")
    return render(request, "projects/project_list.html", {"projects": projects})


def project_detail(request, slug):
    base = Project.objects.all() if request.user.is_staff else Project.objects.visible()
    project = get_object_or_404(base.prefetch_related("media"), slug=slug)
    others = Project.objects.visible().exclude(pk=project.pk).prefetch_related("media")[:3]
    return render(
        request, "projects/project_detail.html",
        {"project": project, "media": list(project.media.all()), "others": others},
    )


def robots_txt(request):
    lines = [
        "User-agent: *",
        f"Disallow: /{settings.ADMIN_URL}",
        f"Sitemap: {request.build_absolute_uri(reverse('sitemap'))}",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")
