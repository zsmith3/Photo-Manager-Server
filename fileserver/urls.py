print("Fileserver urls file")

from django.urls import include, path, re_path
from rest_framework import routers

from . import views
from .membership import urls

router = routers.DefaultRouter()

router.register("files", views.FileViewSet, base_name="files")

router.register("folders", views.FolderViewSet, base_name="folders")

router.register("albums", views.AlbumViewSet, base_name="albums")

router.register("album-files", views.AlbumFileViewSet, base_name="album-files")

router.register("people-groups", views.PersonGroupViewSet, base_name="people-groups")

router.register("people", views.PersonViewSet, base_name="people")

router.register("faces", views.FaceViewSet, base_name="faces")

router.register("geotag-areas", views.GeoTagAreaViewSet, base_name="geotag-areas")

# URL patterns
urlpatterns = [
    path("api/membership", include(urls)),

    path("api/", include(router.urls)),

    path("api/images/faces/<int:face_id>/", views.face_view),

    path("api/images/<int:file_id>/thumbnail/", views.image_thumb_view),
    path("api/images/<int:file_id>/<int:width>x<int:height>/<int:quality>/", views.image_view),
    path("api/images/<int:file_id>/<int:width>x<int:height>/", views.image_view),
    path("api/images/<int:file_id>/", views.image_view)
]
