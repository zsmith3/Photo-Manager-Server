from django.conf import settings
from rest_framework import serializers
from . import models
from .membership import permissions
from .membership.models import AuthGroup


# GeoTag serializer
class GeoTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.GeoTag
        fields = ("id", "latitude", "longitude", "area")


# File serializer (includes geotag data)
class FileSerializer(serializers.ModelSerializer):
    geotag = GeoTagSerializer(allow_null=True)

    # Create new Geotag instance when given in nested update data
    def update(self, instance, validated_data):
        if "access_group" in validated_data:
            user = permissions.get_request_user(self.context["request"])
            if not (settings.DEBUG and not settings.USE_AUTH_IN_DEBUG and user is None):
                access_groups = AuthGroup.objects.filter(group__in=user.groups.all())
                if validated_data["access_group"] not in access_groups:
                    raise serializers.ValidationError({"access_group": "Must be a group to which you belong."})

        if "geotag" in validated_data:
            geotag_data = validated_data.pop("geotag")
            if geotag_data is None:
                if instance.geotag is not None:
                    instance.geotag.delete()
                instance.geotag = None
            elif instance.geotag is None:
                new_geotag = models.GeoTag.objects.create(**geotag_data)
                new_geotag.save()
                instance.geotag = new_geotag
            else:
                GeoTagSerializer().update(instance.geotag, geotag_data)

            if instance.geotag is not None and instance.geotag.latitude is None and instance.geotag.longitude is None and instance.geotag.area is None:
                instance.geotag.delete()
                instance.geotag = None

        return super(FileSerializer, self).update(instance, validated_data)

    class Meta:
        model = models.File
        fields = ("id", "name", "path", "type", "format", "length", "is_starred", "is_deleted", "notes", "timestamp", "width", "height", "orientation", "duration", "geotag",
                  "access_group")
        extra_kwargs = {field: {"read_only": True} for field in fields if field not in ["is_starred", "is_deleted", "notes", "geotag", "orientation", "access_group"]}


# Folder serializer
class FolderSerializer(serializers.ModelSerializer):
    propagate_ag = serializers.BooleanField(write_only=True)

    def update(self, instance, validated_data):
        if "access_group" in validated_data:
            user = permissions.get_request_user(self.context["request"])
            if not (settings.DEBUG and not settings.USE_AUTH_IN_DEBUG and user is None):
                access_groups = AuthGroup.objects.filter(group__in=user.groups.all())
                if validated_data["access_group"] not in access_groups:
                    raise serializers.ValidationError({"access_group": "Must be a group to which you belong."})

            if "propagate_ag" in validated_data and validated_data["propagate_ag"]:
                instance.update_access_group(validated_data.pop("access_group"))
                validated_data.pop("propagate_ag")

        return super(FolderSerializer, self).update(instance, validated_data)

    class Meta:
        model = models.Folder
        fields = ("id", "name", "path", "parent", "file_count", "length", "access_group", "propagate_ag")
        extra_kwargs = {field: {"read_only": True} for field in fields if field not in ["access_group", "propagate_ag"]}


# Album serializer
class AlbumSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Album
        fields = ("id", "name", "file_count", "parent")
        extra_kwargs = {"file_count": {"read_only": True}}


# Album-File relationship serializer (for creation/deletion)
class AlbumFileSerializer(serializers.ModelSerializer):
    # Remove from file from parent albums to avoid duplication
    def create(self, validated_data):
        if not validated_data["album"].get_file_rels().filter(file=validated_data["file"]).exists():
            models.AlbumFile(album=validated_data["album"], file=validated_data["file"]).save()
            validated_data["album"].remove_from_parents(validated_data["file"])
        return validated_data

    class Meta:
        model = models.AlbumFile
        fields = ("id", "file", "album")


# PersonGroup serializer
class PersonGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PersonGroup
        fields = ("id", "name")


# Person serializer (with face count and thumbnail ID)
class PersonSerializer(serializers.ModelSerializer):
    face_count = serializers.SerializerMethodField()
    face_count_confirmed = serializers.SerializerMethodField()
    thumbnail = serializers.SerializerMethodField()

    def get_face_count(self, obj):
        return models.Face.objects.filter(person=obj, status__lt=4).count()

    def get_face_count_confirmed(self, obj):
        return models.Face.objects.filter(person=obj, status__lt=2).count()

    def get_thumbnail(self, obj):
        return obj.thumbnail.id if obj.thumbnail is not None else None

    class Meta:
        model = models.Person
        fields = ("id", "full_name", "face_count", "face_count_confirmed", "thumbnail", "group")
        extra_kwargs = {field: {"read_only": True} for field in ["face_count", "face_count_confirmed", "thumbnail"]}


# Face serializer (includes image file data)
class FaceSerializer(serializers.ModelSerializer):
    file = FileSerializer()

    class Meta:
        model = models.Face
        fields = ("id", "rect_x", "rect_y", "rect_w", "rect_h", "file", "person", "status")
        extra_kwargs = {field: {"read_only": True} for field in fields if field not in ["person", "status"]}


# GeoTagArea serializer
class GeoTagAreaSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.GeoTagArea
        fields = ("id", "name", "address", "latitude", "longitude", "radius")


# ScanFolder serializer
class ScanFolderSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ScanFolder
        fields = ("id", "name", "path", "parent", "file_count")
        extra_kwargs = {field: {"read_only": True} for field in fields}


# Scan serializer
class ScanSerializer(serializers.ModelSerializer):
    lines = serializers.ListField(write_only=True)
    crop_options = serializers.DictField(write_only=True)
    confirm = serializers.BooleanField(write_only=True)
    rects = serializers.ListField(read_only=True)

    class Meta:
        model = models.Scan
        fields = ("id", "name", "format", "folder", "width", "height", "orientation", "lines", "crop_options", "confirm", "rects")
        extra_kwargs = {field: {"read_only": True} for field in fields if field not in ["lines", "crop_options", "confirm"]}

    def validate(self, attrs):
        if "lines" in attrs:
            for line in attrs["lines"]:
                if "axis" not in line or line["axis"] not in [0, 1]:
                    raise serializers.ValidationError({"lines": "Error in 'axis' field on some line(s)."})
                if "pos" not in line or not isinstance(line["pos"], int):
                    raise serializers.ValidationError({"lines": "Error in 'pos' field on some line(s)."})

        return attrs

    def update(self, instance, validated_data):
        if "lines" in validated_data:
            lines = validated_data.pop("lines")
            options = validated_data["crop_options"] if "crop_options" in validated_data else {}
            if "confirm" in validated_data:
                if validated_data["confirm"]:
                    instance.confirm_crop(lines, options)
                validated_data.pop("confirm")
            else:
                rects = instance.get_image_rects(lines, options)
                instance.rects = rects

        return super(ScanSerializer, self).update(instance, validated_data)
