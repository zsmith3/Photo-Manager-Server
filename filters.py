from . import models
import rest_framework_filters as filters


class FileFilter(filters.FilterSet):
    """ Filter set for File model

    Fields
    ------
    `id` : `in`
        Fetches a list of files by IDs
    """

    class Meta:
        model = models.File
        fields = {"id": ["in"], "folder": ["exact"]}


class FolderFilter(filters.FilterSet):
    """ Filter set for Folder model

    Fields
    ------
    `id` : `in`
        Fetches a list of folders by IDs
    `parent` : `isnull`
        Fetches root folders only
    """

    class Meta:
        model = models.Folder
        fields = {"id": ["in"], "parent": ["exact", "isnull"]}
