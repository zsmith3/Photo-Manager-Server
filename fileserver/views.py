# Standard imports
import datetime
import os

# Django imports
from django import http
from rest_framework import viewsets

# Third-party imports
import piexif
from PIL import Image

# Local imports
from . import filters, models, serializers, utils
from .membership import permissions


def log_api(request, *args, **kwargs):
    """ Provide API access to python log files

    Parameters
    ----------
    request : HttpRequest
        The HTTP request

    Returns
    -------
    HttpResponse(content_type="application/json")
        The response log data (may be Forbidden)
    """

    # Ensure request is authorised
    if not request.user.is_superuser:
        return http.HttpResponseForbidden()

    if "start_time" in request.GET:
        start_time = datetime.datetime.strptime(request.GET["start_time"], "%Y-%m-%dT%H:%M:%S")
    else:
        start_time = None

    logs, end_time = utils.read_logs(start_time)

    result = {"end_time": end_time, "logs": logs}

    return http.JsonResponse(result)


def log_view(request, *args, **kwargs):
    """ Provide UI access to python log files

    Parameters
    ----------
    request : HttpRequest
        The HTTP request

    Returns
    -------
    HttpResponse(content_type="application/json")
        An auto-refreshing display of log data (may be Forbidden)
    """

    # Ensure request is authorised
    if not request.user.is_superuser:
        return http.HttpResponseForbidden()

    html = """
    <div id="log"></div>

    <style>
        body {
            margin: 0;
        }

        #log {
            background-color: black;
            color: white;
            font-family: ubuntu;
            padding: 10px;
        }
    </style>

    <script>
        var logdiv = document.getElementById("log");
        var nextstart;
        function load_logs (start_time) {
            var xhr = new XMLHttpRequest();
            xhr.responseType = "json";
            xhr.addEventListener("load", function () {
                var data = this.response;
                var atBottom = window.scrollY + window.innerHeight == document.body.scrollHeight;
                logdiv.innerText += data.logs;
                if (atBottom) window.scrollTo(0, document.body.scrollHeight);
                if (data.logs.length > 0) nextstart = data.end_time;
            });
            xhr.open("GET", "log_api" + (start_time ? ("?start_time=" + start_time) : ""));
            xhr.send();
        }
        load_logs();
        window.setInterval(function () { load_logs(nextstart); }, 5000);
    </script>
    """

    return http.HttpResponse(html)


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
    """ Provide the saved thumbnail image data for a face

    Parameters
    ----------
    face_id : int
        The ID of the face

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

        # Save thumbnail if not already saved
        if face.thumbnail is None:
            face.save_thumbnail()

        if isinstance(face.thumbnail, bytes):
            thumb_bytes = face.thumbnail
        else:
            thumb_bytes = face.thumbnail.tobytes()

        return http.HttpResponse(thumb_bytes, content_type="image/jpeg")
    else:
        return http.HttpResponseNotFound()


class FileViewSet(viewsets.ModelViewSet):
    """ File model viewset

    Provides all information about files.
    Does not provide actual image data.
    """

    permission_classes = (permissions.FileserverPermission, )
    serializer_class = serializers.FileSerializer
    http_method_names = list(filter(lambda n: n not in ["put", "post", "delete"], viewsets.ModelViewSet.http_method_names))
    filter_class = filters.FileFilter
    queryset = models.File.objects.all()
    filter_backends = (filters.BACKEND, filters.CustomSearchFilter)
    pagination_class = filters.CustomPagination
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

    permission_classes = (permissions.FileserverPermission, )
    filter_class = filters.FolderFilter
    queryset = models.Folder.objects.all()
    filter_backends = (filters.BACKEND, filters.CustomSearchFilter)
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

    permission_classes = (permissions.FileserverPermission, )
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
    """ AlbumFile model viewset
    
    Allows creation and deletion of Album-File relationships
    Can be filtered by album and/or file
    """

    permission_classes = (permissions.FileserverPermission, )
    queryset = models.AlbumFile.objects.all()
    serializer_class = serializers.AlbumFileSerializer
    filter_class = filters.AlbumFileFilter


class PersonViewSet(viewsets.ModelViewSet):
    """ Person model viewset

    Provides simple person data when listed.
    For single retrieve, provides IDs of all associated faces.
    """

    permission_classes = (permissions.FileserverPermission, )
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

    permission_classes = (permissions.FileserverPermission, )
    http_method_names = ["get", "patch", "head", "options"]
    serializer_class = serializers.FaceSerializer
    queryset = models.Face.objects.all()
    filter_class = filters.FaceFilter
    pagination_class = filters.CustomPagination


# PersonGroups API
class PersonGroupViewSet(viewsets.ModelViewSet):
    """ PersonGroup model viewset

    Provides data about people groups, and allows modification.
    """

    permission_classes = (permissions.FileserverPermission, )
    http_method_names = list(filter(lambda n: n != "put", viewsets.ModelViewSet.http_method_names))
    serializer_class = serializers.PersonGroupSerializer
    queryset = models.PersonGroup.objects.all()


# GeoTagArea API
class GeoTagAreaViewSet(viewsets.ModelViewSet):
    """ GeoTagArea model viewset

    Provides data about geotag areas, and allows modification.
    """

    permission_classes = (permissions.FileserverPermission, )
    serializer_class = serializers.GeoTagAreaSerializer
    queryset = models.GeoTagArea.objects.all()
