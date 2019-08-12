from django.urls import include, path
from django.contrib import admin

from fileserver.views import log_api, log_view

urlpatterns = [path("admin/logs", log_view), path("admin/log_api", log_api), path("admin/", admin.site.urls), path("fileserver/", include("fileserver.urls"))]
