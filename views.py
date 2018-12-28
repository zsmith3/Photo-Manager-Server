# Standard imports
import os

# Django imports
from django import http
from rest_framework import viewsets

# Third-party imports
import cv2
import piexif
from PIL import Image

# Local imports
from . import filters, models, serializers
from .membership import permissions


def image_view(request, *args, **kwargs):
    """ Provide an image from the file ID, with width/height/quality options

    Parameters
    ----------
    request : HttpRequest
        The HTTP request
    file_id : int
        The ID of the image file
    width : int, optional
        Maximum width of response image
    height : int, optional
        Maximum height of response image
    quality : int
        JPEG quality of response image

    Returns
    -------
    HttpResponse(content_type="image/jpeg")
        The response image if available (may be NotFound, BadRequest or Forbidden)
    """

    # EXIF orientations constant
    rotations = {3: 180, 6: 270, 8: 90}

    # Ensure request is authorised
    if not permissions.FileserverPermission().has_permission(request):
        return http.HttpResponseForbidden()

    # Get file, ensure it exists and is an image
    file_qs = models.File.objects.filter(id=kwargs["file_id"])
    if file_qs.exists():
        file = file_qs.first()
        if not os.path.isfile(file.get_real_path()):
            return http.HttpResponseNotFound()

        if file.type == "image":
            # Scale image if appropriate
            if "width" in kwargs and "height" in kwargs:
                # Determine the desired quality
                if "quality" in kwargs:
                    quality = kwargs["quality"]
                else:
                    quality = 75  # TODO user config?

                # Load image
                image = Image.open(file.get_real_path())

                # Scale down the image
                if file.orientation in [6, 8]:
                    image.thumbnail((kwargs["height"], kwargs["width"]))
                else:
                    image.thumbnail((kwargs["width"], kwargs["height"]))

                # Rotate if needed
                if file.orientation in rotations:
                    image = image.rotate(rotations[file.orientation], expand=True)

                # Create response from image
                response = http.HttpResponse(content_type="image/jpeg")
                image.save(response, "JPEG", quality=quality)
            else:
                # Create response from unaltered image data
                data = open(file.get_real_path(), "rb").read()
                response = http.HttpResponse(data, content_type="image/jpeg")

            response["Content-Disposition"] = "filename=\"%s.%s\"" % (file.name, file.format)
            return response
        else:
            return http.HttpResponseBadRequest()
    else:
        return http.HttpResponseNotFound()


def image_thumb_view(request, *args, **kwargs):
    """ Provide the EXIF thumbnail of an image file if available

    Parameters
    ----------
    file_id : int
        The ID of the image file

    Returns
    -------
    HttpResponse(content_type="image/jpeg")
        The response thumbnail image if available (may be NotFound, BadRequest or Forbidden)
    """

    # Ensure request is authorised
    if not permissions.FileserverPermission().has_permission(request):
        return http.HttpResponseForbidden()

    # Get file, ensure it exists and is an image
    file_qs = models.File.objects.filter(id=kwargs["file_id"])
    if file_qs.exists():
        file = file_qs.first()
        if not os.path.isfile(file.get_real_path()):
            return http.HttpResponseNotFound()

        if file.type == "image":
            # Load exif thumbnail
            exif = piexif.load(file.get_real_path())
            data = exif["thumbnail"]

            # Reject if no thumbnail in EXIF data
            if data is None:
                return http.HttpResponseNotFound()

            # Return the thumbnail response
            response = http.HttpResponse(data, content_type="image/jpeg")
            response["Content-Disposition"] = "filename=\"%s.%s\"" % (file.name, file.format)
            return response
        else:
            return http.HttpResponseBadRequest()
    else:
        return http.HttpResponseNotFound()


def face_view(request, *args, **kwargs):
    """ Provide the image data for a face

    Parameters
    ----------
    face_id : int
        The ID of the face
    quality : int
        JPEG quality of response image

    Returns
    -------
    HttpResponse(content_type="image/jpeg")
        The response image if available (may be NotFound or Forbidden)
    """

    # Ensure request is authorised
    if not permissions.FileserverPermission().has_permission(request):
        return http.HttpResponseForbidden()

    # Get face and ensure it exists
    face_qs = models.Face.objects.filter(id=kwargs["face_id"])
    if face_qs.exists():
        face = face_qs.first()
        if not os.path.isfile(face.file.get_real_path()):
            return http.HttpResponseNotFound()

        # Get the image
        face_image = face.get_image(cv2.COLOR_BGR2RGB, **kwargs)

        # Determine the desired quality
        if "quality" in kwargs:
            quality = kwargs["quality"]
        else:
            quality = 75

        # Return image response
        pil_image = Image.fromarray(face_image)
        response = http.HttpResponse(content_type="image/jpeg")
        pil_image.save(response, "JPEG", quality=quality)
        return response

        # TODO at some point need to look into timings, as seems to be quite slow (although not sure how it compares to old PHP one)
    else:
        return http.HttpResponseNotFound()


class FileViewSet(viewsets.ModelViewSet):
    """ File model viewset

    Provides all information about files.
    Does not provide actual image data.
    """

    permission_classes = (permissions.FileserverPermission,)
    serializer_class = serializers.FileSerializer
    http_method_names = list(filter(lambda n: n not in ["put", "post", "delete"], viewsets.ModelViewSet.http_method_names))
    filter_class = filters.FileFilter
    queryset = models.File.objects.all()
    filter_backends = (filters.BACKEND, filters.CustomSearchFilter)
    search_fields = ("path", "geotag__area__name", "albums__name", "faces__person__full_name")

    # TODO either a) perform all the filter/search/sort/paginate stuff using external modules
    # or b) find a way to return querysets from it

    """ def get_queryset(self):
        if self.action == "list":
            serializer = serializers.FileSerializer(context=self.get_serializer_context())
            files = serializer.extract_files(models.File.objects.all())
            return files
        else:
            return models.File.objects.all() """


class FolderViewSet(viewsets.ReadOnlyModelViewSet):
    """ Folder model viewset

    Provides simple folder data when listed.
    For single retrieve, provides IDs of all child files and folders.
    """

    permission_classes = (permissions.FileserverPermission,)
    filter_class = filters.FolderFilter
    queryset = models.Folder.objects.all()
    filter_backends = (filters.BACKEND, filters.CustomSearchFilter)
    search_fields = ("path",)

    """ def get_queryset(self):
        if self.action == "list":
            return models.Folder.objects.filter(parent=None)
        else:
            return models.Folder.objects.all() """

    def get_serializer_class(self):
        """ Return different serializers for list and retrieve """

        if self.action == "retrieve":
            return serializers.FolderSerializer
        else:
            return serializers.FolderListSerializer

    """ def list(self, request, *args, **kwargs):
        if "query" in self.request.query_params:
            folder = models.Folder.get_from_path(self.request.query_params["query"])
            if folder:
                self.kwargs[self.lookup_field] = folder.id
                self.action = "retrieve"
                return self.retrieve(request, *args, **kwargs)
            else:
                raise http.Http404()
        else:
            return super(FolderViewSet, self).list(request, *args, **kwargs) """


""" # Folder files API
class FolderFileViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.FileserverPermission,)
    serializer_class = serializers.FileSerializer
    # queryset = models.File.objects.all()

    def get_queryset(self):
        folder_qs = models.Folder.objects.filter(id=self.kwargs["folder_pk"])

        if folder_qs.exists():
            folder = folder_qs.first()
            isf = (self.request.query_params["isf"].lower() == "true") if "isf" in self.request.query_params else False
            serializer = serializers.FolderSerializer(context=self.get_serializer_context())
            files = serializer.extract_files(folder.get_files(isf))

            return files
        else:
            raise http.Http404("Folder doesn't exist") """


class AlbumViewSet(viewsets.ModelViewSet):
    """ Album model viewset

    Provides simple album data when listed.
    For single retrieve, provides IDs of all contained files.
    """

    permission_classes = (permissions.FileserverPermission,)
    queryset = models.Album.objects.all()

    """ def get_queryset(self):
        if self.action == "list":
            return models.Album.objects.all()  # .filter(parent=None)
        else:
            return models.Album.objects.all() """

    def get_serializer_class(self):
        """ Return different serializers for list and retrieve """

        if self.action == "retrieve":
            return serializers.AlbumSerializer
        else:
            return serializers.AlbumListSerializer

    """ def list(self, request, *args, **kwargs):
        if "query" in request.query_params:
            album = models.Album.get_from_path(request.query_params["query"])
            if album:
                self.kwargs[self.lookup_field] = album.id
                self.action = "retrieve"
                return self.retrieve(request, *args, **kwargs)
            else:
                raise http.Http404()
        else:
            return super(AlbumViewSet, self).list(request, *args, **kwargs) """


class AlbumFileViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.FileserverPermission,)
    queryset = models.AlbumFile.objects.all()
    serializer_class = serializers.AlbumFileSerializer
    # TODO document

class PersonViewSet(viewsets.ModelViewSet):
    """ Person model viewset

    Provides simple person data when listed.
    For single retrieve, provides IDs of all associated faces.
    """

    permission_classes = (permissions.FileserverPermission,)
    http_method_names = list(filter(lambda n: n != "put", viewsets.ModelViewSet.http_method_names))
    queryset = models.Person.objects.all()

    """ def get_queryset(self):
        return models.Person.objects.all() """

    def get_serializer_class(self):
        """ Return different serializers for list and retrieve """

        if self.action == "retrieve":
            return serializers.PersonSerializer
        else:
            return serializers.PersonListSerializer

    """ def list(self, request, *args, **kwargs):
        if "query" in request.query_params:
            person_qs = models.Person.objects.filter(full_name=request.query_params["query"].rstrip("/"))
            if person_qs:
                person = person_qs.first()
                self.kwargs[self.lookup_field] = person.id
                self.action = "retrieve"
                return self.retrieve(request, *args, **kwargs)
            else:
                raise http.Http404()
        else:
            return super(PersonViewSet, self).list(request, *args, **kwargs) """


# Person faces API TODO decide if this is still necessary
""" class PersonFaceViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.FileserverPermission,)
    serializer_class = serializers.FaceSerializer

    def get_queryset(self):
        person_qs = models.Person.objects.filter(id=self.kwargs["person_pk"])

        if person_qs.exists():
            person = person_qs.first()
            serializer = serializers.PersonSerializer(context=self.get_serializer_context())
            faces = serializer.extract_files(person.get_faces())

            return faces
        else:
            raise http.Http404("Person doesn't exist") """

# NOTE: can change person group with PATCH to person
# TODO create faces API for changing their person (and potentially more features later?)


class FaceViewSet(viewsets.ModelViewSet):
    """ Face model viewset

    Provides all data about faces, as list or single retrieve.
    Also allows modification.
    """

    permission_classes = (permissions.FileserverPermission,)
    http_method_names = ["get", "patch", "head", "options"]
    serializer_class = serializers.FaceSerializer
    queryset = models.Face.objects.all()
    filter_class = filters.FaceFilter


# PersonGroups API
class PersonGroupViewSet(viewsets.ModelViewSet):
    """ PersonGroup model viewset

    Provides data about people groups, and allows modification.
    """

    permission_classes = (permissions.FileserverPermission,)
    http_method_names = list(filter(lambda n: n != "put", viewsets.ModelViewSet.http_method_names))
    serializer_class = serializers.PersonGroupSerializer
    queryset = models.PersonGroup.objects.all()


# GeoTagArea API
class GeoTagAreaViewSet(viewsets.ModelViewSet):
    """ GeoTagArea model viewset

    Provides data about geotag areas, and allows modification.
    """

    permission_classes = (permissions.FileserverPermission,)
    serializer_class = serializers.GeoTagAreaSerializer
    queryset = models.GeoTagArea.objects.all()
