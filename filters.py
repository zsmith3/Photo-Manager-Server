from . import models
from django.core.exceptions import FieldError
import rest_framework_filters as filters
from rest_framework import filters as drf_filters

from . import utils


BACKEND = filters.backends.RestFrameworkFilterBackend


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


class CustomSearchFilter(drf_filters.SearchFilter):
    def filter_queryset(self, request, queryset, view):
        try:
            return super(CustomSearchFilter, self).filter_queryset(request, queryset, view)
        except FieldError:
            # Get search fields
            search_fields = getattr(view, "search_fields", None)

            # Get search query and split into words, sorted by importance (length)
            search_query = request.query_params.get(self.search_param, "").lower()
            queries = [search_query] + sorted(search_query.split(), key=lambda s: -len(s))

            result_list = []
            item_scores = {}
            for item in queryset:
                # Get searchable bodies of text related to the item
                texts = utils._expand_list([utils._get_attr(item, attr.replace("__", ".")) for attr in search_fields])

                # Match each query against each text
                query_matches = [not all([query not in text.lower() for text in texts if text is not None]) for query in queries]
                if True in query_matches:
                    result_list.append(item)
                    # Score match based on number of matches and position of longest match
                    item_scores[item.id] = query_matches.count(True) - query_matches.index(True)

            return sorted(result_list, key=lambda item: -item_scores[item.id])
