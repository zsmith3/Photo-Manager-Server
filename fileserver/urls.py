from django.urls import include, path, re_path
from rest_framework import routers

from . import views
from .membership import urls

router = routers.DefaultRouter()

router.register("files", views.FileViewSet, basename="files")

router.register("folders", views.FolderViewSet, basename="folders")

router.register("albums", views.AlbumViewSet, basename="albums")

router.register("album-files", views.AlbumFileViewSet, basename="album-files")

router.register("people-groups", views.PersonGroupViewSet, basename="people-groups")

router.register("people", views.PersonViewSet, basename="people")

router.register("faces", views.FaceViewSet, basename="faces")

router.register("geotag-areas", views.GeoTagAreaViewSet, basename="geotag-areas")

router.register("scan-folders", views.ScanFolderViewSet, basename="scan-folders")

router.register("scans", views.ScanViewSet, basename="scans")

# URL patterns
urlpatterns = [
    path("api/membership", include(urls)),
    path("api/", include(router.urls)),
    path("api/download/", views.DownloadView.as_view()),
    path("api/images/faces/<int:face_id>/", views.face_view),
] + sum(([
    path(f"api/images/{imgtype}<int:file_id>/thumbnail/", views.image_thumb_view),
    path(f"api/images/{imgtype}<int:file_id>/<int:width>x<int:height>/<int:quality>/", views.image_view),
    path(f"api/images/{imgtype}<int:file_id>/<int:width>x<int:height>/", views.image_view),
    path(f"api/images/{imgtype}<int:file_id>/", views.image_view),
] for imgtype in ["", "scans/"]), [])
