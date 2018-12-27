from . import models
import rest_framework_filters as filters


class FileFilter(filters.FilterSet):
    """ Filter set for File model

    Fields
    ------
    `folder` : `exact`
        Fetches files contained in a folder
    """

    class Meta:
        model = models.File
        fields = {"folder": ["exact"]}


class FolderFilter(filters.FilterSet):
    """ Filter set for Folder model

    Fields
    ------
    `parent` : `exact`, `isnull`
        Fetches subfolders for a folder, or root folders
    """

    class Meta:
        model = models.Folder
        fields = {"parent": ["exact", "isnull"]}

class FaceFilter(filters.FilterSet):
    """ Filter set for Face model

    Fields
    ------
    `person` : `exact`
        Fetches faces for a given person
    """

    class Meta:
        model = models.Face
        fields = {"person": ["exact"]}
