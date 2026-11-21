from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Post, Project


class StaticSitemap(Sitemap):
    priority = 1.0

    def items(self):
        return ["home", "post_list", "project_list"]

    def location(self, item):
        return reverse(item)


class PostSitemap(Sitemap):
    changefreq = "weekly"

    def items(self):
        return Post.objects.published()

    def lastmod(self, obj):
        return obj.updated_at


class ProjectSitemap(Sitemap):
    def items(self):
        return Project.objects.visible()


sitemaps = {"static": StaticSitemap, "posts": PostSitemap, "projects": ProjectSitemap}
