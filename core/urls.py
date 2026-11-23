from django.urls import path

from . import connect_views, make_results, views

urlpatterns = [
    path("", views.home, name="home"),
    path("blog/", views.post_list, name="post_list"),
    path("blog/<slug:slug>/", views.post_detail, name="post_detail"),
    path("ishlar/", views.project_list, name="project_list"),
    path("ishlar/<slug:slug>/", views.project_detail, name="project_detail"),
    path("robots.txt", views.robots_txt, name="robots_txt"),
    path("maxfiylik/", views.privacy, name="privacy"),
    path("api/make/result/", make_results.make_result, name="make_result"),
    path("connect/<str:platform>/", connect_views.connect_start, name="connect_start"),
    path("connect/<str:platform>/callback/", connect_views.connect_callback, name="connect_callback"),
    path("connect/<str:platform>/remove/", connect_views.connect_remove, name="connect_remove"),
    path("connect/<str:platform>/sample/", connect_views.connect_sample, name="connect_sample"),
]
