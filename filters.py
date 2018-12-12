from . import models
import rest_framework_filters as filters


class FileFilter(filters.FilterSet):
    class Meta:
        model = models.File
        fields = {"id": ["in"]}


class FolderFilter(filters.FilterSet):
    class Meta:
        model = models.Folder
        fields = {"id": ["in"], "parent": ["isnull"]}
