# Standard imports
import datetime
import io
import json
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


# Provide API access to python log files (used by log_view)
def log_api(request, *args, **kwargs):
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


# Provide UI access to python log files (for admin page)
def log_view(request, *args, **kwargs):
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


# Provide an image from File or Scan model ID, with width/height/quality options
def image_view(request, *args, **kwargs):
    # EXIF orientations constant
    rotations = {1: 0, 3: 180, 6: 270, 8: 90}

    # Ensure request is authorised
    if not permissions.FileserverPermission().has_permission(request):
        return http.HttpResponseForbidden()

    is_scan = "scans" in request.path

    # Get file, ensure it exists and is an image
    file_qs = (models.Scan if is_scan else models.File).objects.filter(id=kwargs["file_id"])
    if file_qs.exists():
        file = file_qs.first()
        if not os.path.isfile(file.get_real_path()):
            return http.HttpResponseNotFound()

        if is_scan or file.type == "image":
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
                if file.orientation in rotations and file.orientation != 1:
                    image = image.rotate(rotations[file.orientation], expand=True)

                # Create response from image
                response = http.HttpResponse(content_type="image/jpeg")
                image.save(response, "JPEG", quality=quality)
            else:
                exif_orientation = (utils.get_if_exist(json.loads(file.metadata), ["exif", "Image", "Orientation"]) or 1) if not is_scan else 1
                if exif_orientation == file.orientation or exif_orientation not in rotations or file.orientation not in rotations:
                    # Create response from unaltered image data
                    data = open(file.get_real_path(), "rb").read()
                    response = http.HttpResponse(data, content_type="image/jpeg")
                else:
                    # Load and rotate image
                    image = Image.open(file.get_real_path())
                    image = image.rotate(rotations[file.orientation] - rotations[exif_orientation], expand=True)
                    response = http.HttpResponse(content_type="image/jpeg")
                    image.save(response, "JPEG", quality=95)

            response["Content-Disposition"] = "filename=\"%s.%s\"" % (file.name, file.format)
            return response
        else:
            return http.HttpResponseBadRequest()
    else:
        return http.HttpResponseNotFound()


# Provide EXIF thumbnail of image File or Scan if available
def image_thumb_view(request, *args, **kwargs):
    # EXIF orientations constant
    rotations = {3: 180, 6: 270, 8: 90}

    # Ensure request is authorised
    if not permissions.FileserverPermission().has_permission(request):
        return http.HttpResponseForbidden()

    is_scan = "scans" in request.path

    # Get file, ensure it exists and is an image
    file_qs = (models.Scan if is_scan else models.File).objects.filter(id=kwargs["file_id"])
    if file_qs.exists():
        file = file_qs.first()
        if not os.path.isfile(file.get_real_path()):
            return http.HttpResponseNotFound()

        if is_scan or file.type == "image":
            # Load exif thumbnail
            exif = piexif.load(file.get_real_path())
            data = exif["thumbnail"]

            # Reject if no thumbnail in EXIF data
            if data is None:
                return http.HttpResponseNotFound()

            # Rotate if needed
            if file.orientation in rotations:
                image = Image.open(io.BytesIO(data))
                image = image.rotate(rotations[file.orientation], expand=True)
                data_io = io.BytesIO()
                image.save(data_io, "JPEG")
                data = data_io.getvalue()

            # Return the thumbnail response
            response = http.HttpResponse(data, content_type="image/jpeg")
            response["Content-Disposition"] = "filename=\"%s.%s\"" % (file.name, file.format)
            return response
        else:
            return http.HttpResponseBadRequest()
    else:
        return http.HttpResponseNotFound()


# Provide saved thumbnail image for face
def face_view(request, *args, **kwargs):
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


# File API, with filtering by folder/album, searching and pagination
class FileViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.FileserverPermission, )
    serializer_class = serializers.FileSerializer
    http_method_names = list(filter(lambda n: n not in ["put", "post", "delete"], viewsets.ModelViewSet.http_method_names))
    filter_class = filters.FileFilter
    queryset = models.File.objects.all()
    filter_backends = (filters.BACKEND, filters.CustomSearchFilter)
    pagination_class = filters.CustomPagination


# Folder API, with filtering by parent and searching
class FolderViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.FileserverPermission, )
    serializer_class = serializers.FolderSerializer
    filter_class = filters.FolderFilter
    queryset = models.Folder.objects.all()
    filter_backends = (filters.BACKEND, filters.CustomSearchFilter)


# Album API
class AlbumViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.FileserverPermission, )
    serializer_class = serializers.AlbumSerializer
    queryset = models.Album.objects.all()


# Album-File API (for adding/removing files from albums)
class AlbumFileViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.FileserverPermission, )
    queryset = models.AlbumFile.objects.all()
    serializer_class = serializers.AlbumFileSerializer
    filter_class = filters.AlbumFileFilter


# Person API
class PersonViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.FileserverPermission, )
    serializer_class = serializers.PersonSerializer
    http_method_names = list(filter(lambda n: n != "put", viewsets.ModelViewSet.http_method_names))
    queryset = models.Person.objects.all()


# Face API, with filtering by person and pagination
class FaceViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.FileserverPermission, )
    http_method_names = ["get", "patch", "head", "options"]
    serializer_class = serializers.FaceSerializer
    queryset = models.Face.objects.all().order_by("-status", "uncertainty")
    filter_class = filters.FaceFilter
    pagination_class = filters.CustomPagination


# PersonGroup API
class PersonGroupViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.FileserverPermission, )
    http_method_names = list(filter(lambda n: n != "put", viewsets.ModelViewSet.http_method_names))
    serializer_class = serializers.PersonGroupSerializer
    queryset = models.PersonGroup.objects.all()


# GeoTagArea API
class GeoTagAreaViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.FileserverPermission, )
    serializer_class = serializers.GeoTagAreaSerializer
    queryset = models.GeoTagArea.objects.all()


# ScanFolder API, with filtering by parent
class ScanFolderViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.FileserverPermission, )
    serializer_class = serializers.ScanFolderSerializer
    filter_class = filters.ScanFolderFilter
    queryset = models.ScanFolder.objects.all()


# Scan API, with filtering by parent and pagination
class ScanViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.FileserverPermission, )
    http_method_names = list(filter(lambda n: n not in ["put", "post", "delete"], viewsets.ModelViewSet.http_method_names))
    serializer_class = serializers.ScanSerializer
    filter_class = filters.ScanFilter
    queryset = models.Scan.objects.all()
    pagination_class = filters.CustomPagination
