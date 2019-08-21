from . import models
from django.core.exceptions import FieldError
import rest_framework_filters as filters
from rest_framework import filters as drf_filters
from rest_framework import pagination

from . import utils

BACKEND = filters.backends.RestFrameworkFilterBackend


class AlbumFilter(filters.FilterSet):
    """ Filter set for Album model, for use within FileFilter
    
    Fields
    ------
    `id` : `exact`, `in`
        Fetches album(s) by ID
    """
    class Meta:
        model = models.Album
        fields = {"id": ["exact", "in"]}


class FileFilter(filters.FilterSet):
    """ Filter set for File model

    Fields
    ------
    `folder` : `exact`, `in`
        Fetches files contained in a folder (or set of folders)
    `album` : `exact`
        Fetches files contained in an album and its children
    `isf` : bool
        If true, and a folder has been specified, all files from subfolders will also be included
    """

    album = filters.RelatedFilter(AlbumFilter, field_name="album", queryset=models.Album.objects.all(), method="filter_album")

    def __init__(self, data=None, queryset=None, *, relationship=None, **kwargs):
        # NOTE temporarily enable isf for all searches, until front-end is developed further
        if "search" in data or ("folder" in data and "isf" in data and data["isf"] in ["true", "1"]):
            folder_id = data["folder"]
            folder_qs = models.Folder.objects.filter(id=folder_id)
            if folder_qs.exists():
                folder = folder_qs.first()
                all_folders = [folder] + list(folder.get_children(True))
                data = {key: data[key] for key in data if key != "folder"}
                data["folder__in"] = ",".join([str(folder.id) for folder in all_folders])

        return super(FileFilter, self).__init__(data, queryset, relationship=relationship, **kwargs)

    def filter_album(self, qs, name, value):
        all_files = value.get_files()

        return qs & all_files

    class Meta:
        model = models.File
        fields = {"folder": ["exact", "in"]}


class FolderFilter(filters.FilterSet):
    """ Filter set for Folder model

    Fields
    ------
    `id` : `in`
        Used internally to fetch full subfolder tree
    `parent` : `exact`, `isnull`
        Fetches subfolders for a folder, or root folders
    `isf` : bool
        If true, and a parent folder has been specified, the full subfolder tree will be fetched
    """
    def __init__(self, data=None, queryset=None, *, relationship=None, **kwargs):
        # NOTE temporarily enable isf for all searches, until front-end is developed further
        if "search" in data or ("parent" in data and "isf" in data and data["isf"] in ["true", "1"]):
            parent_id = data["parent"]
            parent_qs = models.Folder.objects.filter(id=parent_id)
            if parent_qs.exists():
                parent = parent_qs.first()
                all_folders = list(parent.get_children(True))
                data = {key: data[key] for key in data if key != "parent"}
                data["id__in"] = ",".join([str(folder.id) for folder in all_folders])

        return super(FolderFilter, self).__init__(data, queryset, relationship=relationship, **kwargs)

    class Meta:
        model = models.Folder
        fields = {"id": ["in"], "parent": ["exact", "isnull"]}


class FaceFilter(filters.FilterSet):
    """ Filter set for Face model

    Fields
    ------
    `person` : `exact`
        Fetches faces for a given person
    `status` : `exact`, `lt`, `gt`
        Used to ignore unwanted faces (defaults to less than 4)
    """
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


class AlbumFileFilter(filters.FilterSet):
    """ Filter set for AlbumFile model
    
    Fields
    ------
    `file` : `exact`
        Restricts relationships to a specific file
    `album` : `exact`
        Finds relationships with album or its children
    """

    album = filters.RelatedFilter(AlbumFilter, field_name="album", queryset=models.Album.objects.all(), method="filter_album")

    def filter_album(self, qs, name, value):
        all_albums = [value] + list(value.get_children(True))
        return qs.filter(album__in=all_albums)

    class Meta:
        model = models.AlbumFile
        fields = {"file": ["exact"]}


class CustomSearchFilter(drf_filters.SearchFilter):
    """ Filter class for custom file-searching method

    Works on File and Folder models.
    """
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


class CustomPagination(pagination.PageNumberPagination):
    """ Pagination class which allows for variable page size """

    page_size = 100
    page_size_query_param = "page_size"
