from rest_framework import status, viewsets, response
from django import http
from django.shortcuts import redirect

from PIL import Image
import cv2
# import exifread
import os
import piexif

from . import models
from . import filters
from . import serializers
from .membership import permissions


# Image API
def image_view(request, *args, **kwargs):
    # EXIF orientations constant
    rotations = {3: 180, 6: 270, 8: 90}

    if not permissions.FileserverPermission().has_permission(request):
        return http.HttpResponseForbidden()

    file_qs = models.File.objects.filter(id=kwargs["file_id"])
    if file_qs.exists():
        file = file_qs.first()
        if not os.path.isfile(file.get_real_path()):
            return http.HttpResponseNotFound()

        if file.type == "image":
            if "width" in kwargs and "height" in kwargs:
                if "quality" in kwargs:
                    quality = kwargs["quality"]
                else:
                    quality = 75  # TODO user config?

                image = Image.open(file.get_real_path())

                if file.orientation in [6, 8]:
                    image.thumbnail((kwargs["height"], kwargs["width"]))
                else:
                    image.thumbnail((kwargs["width"], kwargs["height"]))

                if file.orientation in rotations:
                    image = image.rotate(rotations[file.orientation], expand=True)

                response = http.HttpResponse(content_type="image/jpeg")
                image.save(response, "JPEG", quality=quality)
            else:
                data = open(file.get_real_path(), "rb").read()
                response = http.HttpResponse(data, content_type="image/jpeg")

            response["Content-Disposition"] = "filename=\"%s.%s\"" % (file.name, file.format)
            return response
        else:
            return http.HttpResponseBadRequest()
    else:
        return http.HttpResponseNotFound()


# EXIF thumbnail API
def image_thumb_view(request, *args, **kwargs):
    if not permissions.FileserverPermission().has_permission(request):
        return http.HttpResponseForbidden()

    file_qs = models.File.objects.filter(id=kwargs["file_id"])
    if file_qs.exists():
        file = file_qs.first()
        if not os.path.isfile(file.get_real_path()):
            return http.HttpResponseNotFound()

        if file.type == "image":
            exif = piexif.load(file.get_real_path())
            data = exif["thumbnail"]

            if data is None:
                return http.HttpResponseNotFound()

            response = http.HttpResponse(data, content_type="image/jpeg")
            response["Content-Disposition"] = "filename=\"%s.%s\"" % (file.name, file.format)
            return response
        else:
            return http.HttpResponseBadRequest()
    else:
        return http.HttpResponseNotFound()


# Face image API
def face_view(request, *args, **kwargs):
    if not permissions.FileserverPermission().has_permission(request):
        return http.HttpResponseForbidden()

    face_qs = models.Face.objects.filter(id=kwargs["face_id"])
    if face_qs.exists():
        face = face_qs.first()
        if not os.path.isfile(face.file.get_real_path()):
            return http.HttpResponseNotFound()

        face_image = face.get_image(cv2.COLOR_BGR2RGB, **kwargs)

        pil_image = Image.fromarray(face_image)
        response = http.HttpResponse(content_type="image/jpeg")
        pil_image.save(response, "JPEG", quality=75)
        return response

        # TODO at some point need to look into timings, as seems to be quite slow (although not sure how it compares to old PHP one)

        # Apply image orientation TODO
        # image->rotateImage("black", preRot)
    else:
        return http.HttpResponseNotFound()


# File API
class FileViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.FileserverPermission,)
    serializer_class = serializers.FileSerializer
    http_method_names = list(filter(lambda n: n not in ["put", "post", "delete"], viewsets.ModelViewSet.http_method_names))
    filter_class = filters.FileFilter
    queryset = models.File.objects.all()

    # TODO either a) perform all the filter/search/sort/paginate stuff using external modules
    # or b) find a way to return querysets from it

    """ def get_queryset(self):
        if self.action == "list":
            serializer = serializers.FileSerializer(context=self.get_serializer_context())
            files = serializer.extract_files(models.File.objects.all())
            return files
        else:
            return models.File.objects.all() """


# Folder API
class FolderViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.FileserverPermission,)
    filter_class = filters.FolderFilter
    queryset = models.Folder.objects.all()

    """ def get_queryset(self):
        if self.action == "list":
            return models.Folder.objects.filter(parent=None)
        else:
            return models.Folder.objects.all() """

    def get_serializer_class(self):
        if self.action == "retrieve":
            return serializers.FolderSerializer
        else:
            return serializers.RootFolderSerializer

    def list(self, request, *args, **kwargs):
        if "query" in self.request.query_params:
            folder = models.Folder.get_from_path(self.request.query_params["query"])
            if folder:
                self.kwargs[self.lookup_field] = folder.id
                self.action = "retrieve"
                return self.retrieve(request, *args, **kwargs)
            else:
                raise http.Http404()
        else:
            return super(FolderViewSet, self).list(request, *args, **kwargs)


# Folder files API
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
            raise http.Http404("Folder doesn't exist")


# Album API
class AlbumViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.FileserverPermission,)

    def get_queryset(self):
        if self.action == "list":
            return models.Album.objects.all() #.filter(parent=None)
        else:
            return models.Album.objects.all()

    def get_serializer_class(self):
        if self.action == "retrieve":
            return serializers.AlbumSerializer
        else:
            return serializers.RootAlbumsSerializer

    def list(self, request, *args, **kwargs):
        if "query" in request.query_params:
            album = models.Album.get_from_path(request.query_params["query"])
            if album:
                self.kwargs[self.lookup_field] = album.id
                self.action = "retrieve"
                return self.retrieve(request, *args, **kwargs)
            else:
                raise http.Http404()
        else:
            return super(AlbumViewSet, self).list(request, *args, **kwargs)


# Album files API
class AlbumFileViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.FileserverPermission,)
    http_method_names = list(filter(lambda n: n not in ["put", "patch"], viewsets.ModelViewSet.http_method_names))

    def get_queryset(self):
        album_qs = models.Album.objects.filter(id=self.kwargs["album_pk"])

        if album_qs.exists():
            album = album_qs.first()

            if self.action == "destroy":
                album_files = album.get_file_rels()
                return album_files
            else:
                serializer = serializers.AlbumSerializer(context=self.get_serializer_context())
                files = serializer.extract_files(album.get_files())
                return files
        else:
            raise http.Http404("Album doesn't exist")

    def get_serializer_class(self):
        if self.action == "create":
            return serializers.AlbumFileSerializer
        else:
            return serializers.FileSerializer

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        kwargs["context"] = self.get_serializer_context()

        if self.action == "create" and self.request.data:
            kwargs["many"] = True

        return serializer_class(*args, **kwargs)

    def create(self, request, *args, **kwargs):
        for item in request.data:
            item["album"] = kwargs["album_pk"]

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return redirect("/fileserver/api/albums/")

    def destroy(self, request, *args, **kwargs):
        self.lookup_url_kwarg = self.lookup_field
        self.lookup_field = "file"
        instance = self.get_object()
        self.perform_destroy(instance)
        return response.Response(status=status.HTTP_204_NO_CONTENT)


# Person API
class PersonViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.FileserverPermission,)
    http_method_names = list(filter(lambda n: n != "put", viewsets.ModelViewSet.http_method_names))

    def get_queryset(self):
        return models.Person.objects.all()

    def get_serializer_class(self):
        if self.action in "list":
            return serializers.RootPersonSerializer
        else:
            return serializers.PersonSerializer

    def list(self, request, *args, **kwargs):
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
            return super(PersonViewSet, self).list(request, *args, **kwargs)


# Person faces API
class PersonFaceViewSet(viewsets.ReadOnlyModelViewSet):
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
            raise http.Http404("Person doesn't exist")

# NOTE: can change person group with PATCH to person
# TODO create faces API for changing their person (and potentially more features later?)


# Faces API
class FaceViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.FileserverPermission,)
    http_method_names = ["get", "patch", "head", "options"]
    serializer_class = serializers.FaceSerializer
    queryset = models.Face.objects.all()


# PersonGroups API
class PersonGroupViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.FileserverPermission,)
    http_method_names = list(filter(lambda n: n != "put", viewsets.ModelViewSet.http_method_names))
    serializer_class = serializers.PersonGroupSerializer
    queryset = models.PersonGroup.objects.all()


# GeoTagArea API
class GeoTagAreaViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.FileserverPermission,)
    serializer_class = serializers.GeoTagAreaSerializer
    queryset = models.GeoTagArea.objects.all()


# TODO apply both filtering and searching to non-folder views
