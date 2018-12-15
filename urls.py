from django.urls import include, path, re_path
from rest_framework.routers import Route
from rest_framework_nested import routers

from . import views
from .membership import urls

router = routers.DefaultRouter()

router.register("files", views.FileViewSet, base_name="files")

router.register("folders", views.FolderViewSet, base_name="folders")
folders_router = routers.NestedDefaultRouter(router, "folders", lookup="folder")
# folders_router.register("files", views.FolderFileViewSet, base_name="folder-files")

router.register("albums", views.AlbumViewSet, base_name="albums")
albums_router = routers.NestedDefaultRouter(router, "albums", lookup="album")
albums_router.register("files", views.AlbumFileViewSet, base_name="album-files")

router.register("people-groups", views.PersonGroupViewSet, base_name="people-groups")

router.register("people", views.PersonViewSet, base_name="people")
people_router = routers.NestedDefaultRouter(router, "people", lookup="person")
# people_router.register("faces", views.PersonFaceViewSet, base_name="person-faces")

router.register("faces", views.FaceViewSet, base_name="faces")

router.register("geotag-areas", views.GeoTagAreaViewSet, base_name="geotag-areas")

# URL patterns
urlpatterns = [
    # path("", views.index, name="index"),
    # path("api/", include(router.urls)),
    path("api/membership", include(urls)),
    # path("api/folders/<path:folder_path>/", views.FolderView.as_view()),
    # re_path("api/folders/?$", views.RootFoldersView.as_view()),
    # path("api/albums/<path:album_path>/", views.AlbumView.as_view()),
    # re_path("api/albums/?$", views.RootAlbumsView.as_view()),
    # path("api/albums/<path:album_path>/", views.album_redirect),
    # path("api/albums/<int:album_id>/", views.AlbumsView.as_view()),
    # re_path("api/albums/?$", views.RootAlbumsView.as_view()),

    # re_path("api/albums/?$", views.RootAlbumsView.as_view()),
    # path("api/albums/<int:pk>/", views.AlbumView.as_view()),
    # path("api/albums/<int:pk>/files/<int:>", views.AlbumFilesView.as_view()),

    path("api/", include(router.urls)),
    path("api/", include(folders_router.urls)),
    path("api/", include(albums_router.urls)),
    path("api/", include(people_router.urls)),

    path("api/images/faces/<int:face_id>/<int:height>/<int:quality>/", views.face_view),
    path("api/images/faces/<int:face_id>/<int:height>/", views.face_view),
    path("api/images/faces/<int:face_id>/", views.face_view),

    path("api/images/<int:file_id>/thumbnail/", views.image_thumb_view),
    path("api/images/<int:file_id>/<int:width>x<int:height>/<int:quality>/", views.image_view),
    path("api/images/<int:file_id>/<int:width>x<int:height>/", views.image_view),
    path("api/images/<int:file_id>/", views.image_view)
]
