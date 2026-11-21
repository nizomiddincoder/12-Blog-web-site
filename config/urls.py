from django.conf import settings
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path, re_path

from core.media_views import serve_media
from core.sitemaps import sitemaps

admin.site.site_header = "Boshqaruv paneli"
admin.site.site_title = "Boshqaruv paneli"
admin.site.index_title = "Sayt va Telegram kanalni boshqarish"
admin.site.enable_nav_sidebar = False  # o'rniga templates/admin/base_site.html dagi qora panel

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    path("", include("core.urls")),
]

if settings.SERVE_MEDIA:
    media_prefix = settings.MEDIA_URL.strip("/")
    urlpatterns += [re_path(rf"^{media_prefix}/(?P<path>.+)$", serve_media, name="media")]
