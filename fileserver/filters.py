from . import models
from django.core.exceptions import FieldError
import rest_framework_filters as filters
from rest_framework import filters as drf_filters
from rest_framework import pagination

from . import utils

BACKEND = filters.backends.RestFrameworkFilterBackend


# Filter albums by by ID(s) (used within FileFilter)
class AlbumFilter(filters.FilterSet):
    class Meta:
        model = models.Album
        fields = {"id": ["exact", "in"]}


# Filter files/scan-files by folder(s) (with isf option to include files from subfolders)
class BaseFileFilter(filters.FilterSet):
    def __init__(self, data=None, queryset=None, *, relationship=None, **kwargs):
        if "folder" in data and "isf" in data and data["isf"] in ["true", "1"]:
            folder_id = data["folder"]
            folder_qs = self.folder_cls().objects.filter(id=folder_id)
            if folder_qs.exists():
                folder = folder_qs.first()
                all_folders = [folder] + list(folder.get_children(True))
                data = {key: data[key] for key in data if key != "folder"}
                data["folder__in"] = ",".join([str(folder.id) for folder in all_folders])

        return super(BaseFileFilter, self).__init__(data, queryset, relationship=relationship, **kwargs)


# Filter files by folder(s)/album
class FileFilter(BaseFileFilter):
    album = filters.RelatedFilter(AlbumFilter, field_name="album", queryset=models.Album.objects.all(), method="filter_album")

    def filter_album(self, qs, name, value):
        all_files = value.get_files()

        return qs & all_files

    class Meta:
        model = models.File
        fields = {"folder": ["exact", "in"]}


# Filter folders/scan-folders by ID/parent (with isf option to include subfolders)
class BaseFolderFilter(filters.FilterSet):
    def __init__(self, data=None, queryset=None, *, relationship=None, **kwargs):
        if "parent" in data and "isf" in data and data["isf"] in ["true", "1"]:
            parent_id = data["parent"]
            parent_qs = self.folder_cls().objects.filter(id=parent_id)
            if parent_qs.exists():
                parent = parent_qs.first()
                all_folders = list(parent.get_children(True))
                data = {key: data[key] for key in data if key != "parent"}
                if len(all_folders) > 0:
                    data["id__in"] = ",".join([str(folder.id) for folder in all_folders])
                else:
                    data["id__in"] = "-1"

        return super(BaseFolderFilter, self).__init__(data, queryset, relationship=relationship, **kwargs)


# Standard file folder filter
class FolderFilter(BaseFolderFilter):
    class Meta:
        model = models.Folder
        fields = {"id": ["in"], "parent": ["exact", "isnull"]}


# Filter faces by person/status
class FaceFilter(filters.FilterSet):
    def __init__(self, data=None, *args, **kwargs):
        # Default to status=lt__4
        if data is not None:
            data = data.copy()

            done = False
            for name in data:
                if "status" in name:
                    done = True

            if not done:
                data["status__lt"] = "4"

        super(FaceFilter, self).__init__(data, *args, **kwargs)

    class Meta:
        model = models.Face
        fields = {"person": ["exact"], "status": ["exact", "lt", "gt"]}


# Filter album-file relationships by file/album (includes children of album)
class AlbumFileFilter(filters.FilterSet):
    album = filters.RelatedFilter(AlbumFilter, field_name="album", queryset=models.Album.objects.all(), method="filter_album")

    def filter_album(self, qs, name, value):
        all_albums = [value] + list(value.get_children(True))
        return qs.filter(album__in=all_albums)

    class Meta:
        model = models.AlbumFile
        fields = {"file": ["exact"]}


# Scan file folder filter
class ScanFolderFilter(BaseFolderFilter):
    class Meta:
        model = models.ScanFolder
        fields = {"id": ["in"], "parent": ["exact", "isnull"]}


# Filter scan files by folder(s)
class ScanFilter(BaseFileFilter):
    def __init__(self, data=None, *args, **kwargs):
        # Default to done_output=False
        if data is not None:
            data = data.copy()

            done = False
            for name in data:
                if "done_output" in name:
                    done = True

            if not done:
                data["done_output"] = False

        super(ScanFilter, self).__init__(data, *args, **kwargs)

    class Meta:
        model = models.Scan
        fields = {"folder": ["exact", "in"], "done_output": ["exact"]}


# Custom search method (for File and Folder models)
class CustomSearchFilter(drf_filters.SearchFilter):
    def filter_queryset(self, request, queryset, view):
        # Get search query and split into words, sorted by importance (length)
        search_query = request.query_params.get(self.search_param, "").lower()
        queries = ([search_query] if search_query.strip().count(" ") > 0 else []) + sorted(search_query.split(), key=lambda s: -len(s))

        if len(queries) == 0:
            return queryset

        all_file_sets = []

        # Get files by name
        all_file_sets.append(utils.get_full_set(queries, lambda q: queryset.filter(name__icontains=q)))

        if queryset.model == models.File:
            # Get files via people
            people = utils.get_full_set(queries, lambda q: models.Person.objects.filter(full_name__icontains=q))
            faces = utils.get_full_set(people, lambda p: p.get_faces().filter(file__in=queryset))
            all_file_sets.append(utils.unique_and_sort([face.file for face in faces]))

            # Get files via geotags
            geotag_name_areas = utils.get_full_set(queries, lambda q: models.GeoTagArea.objects.filter(name__icontains=q))
            geotag_address_areas = utils.get_full_set(queries, lambda q: models.GeoTagArea.objects.filter(address__icontains=q))
            geotag_areas = utils.get_full_set([geotag_name_areas, geotag_address_areas])
            all_file_sets.append(utils.get_full_set(geotag_areas, lambda a: queryset.filter(geotag__area=a)))

            # Get files via albums
            albums = utils.get_full_set(queries, lambda q: models.Album.objects.filter(name__icontains=q))
            all_file_sets.append(utils.get_full_set(albums, lambda a: a.get_files().intersection(queryset)))

            # Get files via folders
            folders = utils.get_full_set(queries, lambda q: models.Folder.objects.filter(name__icontains=q))
            all_file_sets.append(utils.get_full_set(folders, lambda f: f.get_files(True, queryset)))

        # Combine all file sets
        all_files = utils.get_full_set(all_file_sets)

        return all_files


# Pagination class (with variable page size)
class CustomPagination(pagination.PageNumberPagination):
    page_size = 100
    page_size_query_param = "page_size"
