# Standard imports
import datetime
import io
import json
import os

# Django imports
from django import http
from rest_framework import viewsets, response, parsers
from rest_framework_msgpack.parsers import MessagePackParser
from django.core.files.storage import FileSystemStorage

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
    file_qs = filters.PermissionFilter().filter_queryset(request, file_qs, None)
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
    file_qs = filters.PermissionFilter().filter_queryset(request, file_qs, None)
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
    face_qs = filters.PermissionFilter().filter_queryset(request, face_qs, None)
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


# Track total size of recent uploads
# this feels hacky
all_upload_sizes = []


# File API, with filtering by folder/album, searching and pagination
class FileViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.FileSerializer
    http_method_names = list(filter(lambda n: n not in ["put", "post", "delete"], viewsets.ModelViewSet.http_method_names))
    filter_class = filters.FileFilter
    queryset = models.File.objects.all().order_by("folder", "name")
    filter_backends = (filters.BACKEND, filters.CustomSearchFilter, filters.PermissionFilter)
    pagination_class = filters.CustomPagination
    parser_classes = (parsers.JSONParser, MessagePackParser, parsers.MultiPartParser)
    permission_classes = (permissions.getLinkPermissions(["POST"]),)

    def create(self, request):
        file_uploaded = request.FILES.get("file_uploaded")
        if not file_uploaded:
            return response.Response({"file_uploaded": "This field is required."}, 400)
        if file_uploaded.size > 50 * 1024 * 1024:
            return response.Response({"file_uploaded": "Max file size 50MB."}, 400)
        recent_upload_size = sum([t[1] for t in all_upload_sizes if (datetime.datetime.now() - t[0]).total_seconds() < 24 * 60 * 60])
        if recent_upload_size + file_uploaded.size > 1024 ** 3:
            return response.Response({"file_uploaded": "Max total upload size 1GB per 24 hours."}, 400)

        if "folder" not in request.data or not request.data["folder"].isdigit():
            return response.Response({"folder": "This field is required, and should be a single integer."}, 400)
        folder_id = int(request.data["folder"])
        folder_qs = models.Folder.objects.filter(id=folder_id)
        folder_qs = filters.PermissionFilter().filter_queryset(request, folder_qs, None)
        if not folder_qs.exists():
            return response.Response({"folder": "Invalid folder ID provided."}, 400)
        folder = folder_qs.first()
        if not folder.allow_upload:
            return response.Response({"folder": "Upload to this folder is not allowed."}, 403)
        folder_path = folder.get_real_path().rstrip("/")

        all_upload_sizes.append((datetime.datetime.now(), file_uploaded.size))
        fs = FileSystemStorage(folder_path)
        filename = fs.save(file_uploaded.name, file_uploaded)

        file = models.File.from_fs(filename, folder)

        return response.Response(serializers.FileSerializer(file).data)


# Folder API, with filtering by parent and searching
class FolderViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.FolderSerializer
    http_method_names = list(filter(lambda n: n not in ["put", "post", "delete"], viewsets.ModelViewSet.http_method_names))
    filter_class = filters.FolderFilter
    queryset = models.Folder.objects.all().order_by("parent", "name")
    filter_backends = (filters.BACKEND, filters.CustomSearchFilter, filters.PermissionFilter)


# Album API
class AlbumViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.AlbumSerializer
    queryset = models.Album.objects.all()
    filter_backends = (filters.BACKEND, filters.PermissionFilter)


# Album-File API (for adding/removing files from albums)
class AlbumFileViewSet(viewsets.ModelViewSet):
    queryset = models.AlbumFile.objects.all()
    serializer_class = serializers.AlbumFileSerializer
    filter_class = filters.AlbumFileFilter


# Person API
class PersonViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.PersonSerializer
    queryset = models.Person.objects.all()
    filter_backends = (filters.BACKEND, filters.PermissionFilter)


# Face API, with filtering by person and pagination
class FaceViewSet(viewsets.ModelViewSet):
    http_method_names = ["get", "patch", "head", "options"]
    serializer_class = serializers.FaceSerializer
    queryset = models.Face.objects.all().order_by("-status", "uncertainty", "id")
    filter_backends = (filters.BACKEND, filters.PermissionFilter)
    filter_class = filters.FaceFilter
    pagination_class = filters.CustomPagination


# PersonGroup API
class PersonGroupViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.PersonGroupSerializer
    queryset = models.PersonGroup.objects.all()
    filter_backends = (filters.BACKEND, filters.PermissionFilter)


# GeoTagArea API
class GeoTagAreaViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.GeoTagAreaSerializer
    queryset = models.GeoTagArea.objects.all()
    filter_backends = (filters.BACKEND, filters.PermissionFilter)


# ScanFolder API, with filtering by parent
class ScanFolderViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = serializers.ScanFolderSerializer
    filter_class = filters.ScanFolderFilter
    queryset = models.ScanFolder.objects.all()
    filter_backends = (filters.BACKEND, filters.PermissionFilter)


# Scan API, with filtering by parent and pagination
class ScanViewSet(viewsets.ModelViewSet):
    http_method_names = list(filter(lambda n: n not in ["put", "post", "delete"], viewsets.ModelViewSet.http_method_names))
    serializer_class = serializers.ScanSerializer
    filter_backends = (filters.BACKEND, filters.PermissionFilter)
    filter_class = filters.ScanFilter
    queryset = models.Scan.objects.all()
    pagination_class = filters.CustomPagination
