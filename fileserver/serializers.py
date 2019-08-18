from rest_framework import serializers
from . import models, utils


# Filter files by search term
def filter_search(self, files):
    if "search" in self.context["request"].query_params:
        # Get search query and split into words, sorted by importance (length)
        search_query = self.context["request"].query_params["search"].lower()
        queries = [search_query] + sorted(search_query.split(), key=lambda s: -len(s))

        new_files = []
        file_scores = {}
        for file in files:
            # Get searchable bodies of text related to the file
            texts = utils.expand_list([utils.get_attr(file, attr) for attr in self.filter_search_attrs])
            # Match each query against each text
            query_matches = [not all([query not in text.lower() for text in texts if text is not None]) for query in queries]
            if True in query_matches:
                new_files.append(file)
                # Score match based on number of matches and position of longest match
                file_scores[file.id] = query_matches.count(True) - query_matches.index(True)
        # Return files matched files sorted by score
        return sorted(new_files, key=lambda file: -file_scores[file.id])
        # TODO user options for case sensitive and individual word matching
    else:
        return files


serializers.ModelSerializer.filter_search_attrs = ["name", "geotag.area.name", "albums.name", "faces.person.full_name"]
serializers.ModelSerializer.filter_search = filter_search

# Functions to fetch files by filter
filter_functions = {
    "*": lambda all_files, query: all_files,
    "G": lambda all_files, query: [file for file in all_files if utils.get_attr(file, "geotag.area.id") == int(query)],
    "A": lambda all_files, query: [file for file in all_files if int(query) in utils.get_attr(file, "albums.id")],
    "F": lambda all_files, query: [file for file in all_files if file.type == query]
}


# Filter files by filters
def apply_filters(self, files):
    if "filter" in self.context["request"].query_params:
        # Get filters from query string
        filters_string = self.context["request"].query_params["filter"]
        filters = filters_string.split("/")
        start_action = filters[0][0].upper()
        if start_action == "E":
            filtered_files = []
        else:
            filtered_files = list(files)

        for filter_string in filters[1:]:
            # Get action and find new files to filter against
            action = filter_string[0].upper()
            new_files = filter_functions[filter_string[1].upper()](files, filter_string[2:])

            # Change file set based on filter
            if action == "I":
                filtered_files += new_files
            elif action == "E":
                filtered_files = [file for file in filtered_files if file not in new_files]
            elif action == "O":
                filtered_files = [file for file in filtered_files if file in new_files]
            else:
                pass

        return filtered_files
    else:
        return files


serializers.ModelSerializer.apply_filters = apply_filters


# Sort files
def sort_files(self, files):
    files.sort(key=lambda file: utils.get_attr(file, "file_id") or file.id)

    # Sorting for faces
    files.sort(key=lambda file: utils.get_attr(file, "file.file_id") or 0)
    files.sort(key=lambda file: utils.get_attr(file, "uncertainty") or 0)
    files.sort(key=lambda file: utils.get_attr(file, "status") or 0)

    # TODO other sorting methods

    return files


serializers.ModelSerializer.sort_files = sort_files


# Paginate files
def paginate_files(self, files):
    try:
        page = int(utils.get_if_exist(self.context["request"].query_params, ["page"]) or 1)
        fpp = utils.get_if_exist(self.context["request"].query_params, ["fpp"]) or 50  # TODO get from user config and platform
        if fpp == "inf":
            fpp = len(files)
        else:
            fpp = int(fpp)
    except:
        raise ValueError  # TODO raise http error (bad request)

    return files[max((page - 1) * fpp, 0):min(page * fpp, len(files))]


serializers.ModelSerializer.paginate_files = paginate_files


# Extract files to output (filter, search, sort, paginate)
def view_extract_files(self, files, paginate=True):
    files = list(files)
    files = self.apply_filters(files)
    files = self.filter_search(files)
    files = self.sort_files(files)
    if paginate:
        files = self.paginate_files(files)

    return files


serializers.ModelSerializer.extract_files = view_extract_files


# Serializer for GeoTag model
class GeoTagSerializer(serializers.ModelSerializer):
    """ GeoTag model serializer """
    class Meta:
        model = models.GeoTag
        fields = ("id", "latitude", "longitude", "area")


# Serializer for File model
class FileSerializer(serializers.ModelSerializer):
    """ File model serializer

    Includes geotag data (TODO maybe remove this).
    Allows modification of: id, is_starred, is_deleted, geotag
    """

    geotag = GeoTagSerializer()

    def update(self, instance, validated_data):
        """ Create new Geotag when nested in update data """

        if "geotag" in validated_data:
            geotag_data = validated_data.pop("geotag")
            new_geotag = models.GeoTag.objects.create(**geotag_data)
            new_geotag.save()
            instance.geotag = new_geotag

        return super(FileSerializer, self).update(instance, validated_data)

    class Meta:
        model = models.File
        fields = ("id", "name", "path", "type", "format", "length", "is_starred", "is_deleted", "timestamp", "width", "height", "orientation", "duration", "geotag")
        extra_kwargs = {field: {"read_only": True} for field in fields if field not in ["id", "is_starred", "is_deleted", "geotag"]}


# Compact serializer for File model TODO confirm no longer needed
""" class SimpleImageSerializer(FileSerializer):
    class Meta:
        model = models.File
        fields = [field for field in FileSerializer.Meta.fields if field not in ["path", "type", "length", "timestamp", "duration", "geotag"]] """


class FolderListSerializer(serializers.ModelSerializer):
    """ Folder model serializer, for list view

    Provides data about folder, but not its children.
    """
    class Meta:
        model = models.Folder
        fields = ("id", "name", "path", "parent", "file_count", "length")


class FolderSerializer(FolderListSerializer):
    """ Folder model serializer, for retrieve view

    Provides data about folder and its child folder/file IDs.
    """

    # folders = serializers.SerializerMethodField()
    # files = serializers.SerializerMethodField()

    def get_folders(self, obj):
        isf = (self.context["request"].query_params["isf"].lower() == "true") if "isf" in self.context["request"].query_params else False
        folders = self.extract_files(obj.get_children(isf), paginate=False)
        return [folder.id for folder in folders]
        """ serializer = FileSerializer(folders, many=True)
        return serializer.data """
    def get_files(self, obj):
        isf = (self.context["request"].query_params["isf"].lower() == "true") if "isf" in self.context["request"].query_params else False
        files = self.extract_files(obj.get_files(isf), paginate=False)
        return [file.id for file in files]
        # TODO apply extraction to non-folder viewsets
        """ serializer = FileSerializer(files, many=True)
        return serializer.data """
    class Meta:
        model = models.Folder
        fields = FolderListSerializer.Meta.fields  # + ("folders", "files")


class AlbumListSerializer(serializers.ModelSerializer):
    """ Album model serializer, for list view

    Provides data about album, but not contained files.
    """
    class Meta:
        model = models.Album
        fields = ("id", "name", "file_count", "parent")  # ("children", "parent")
        # extra_kwargs = {"parent": {"write_only": True}}


class AlbumSerializer(serializers.ModelSerializer):
    """ Album model serializer, for retrieve view

    Provides data about album and contained file IDs.
    """

    files = serializers.SerializerMethodField()

    def get_files(self, obj):
        files = self.extract_files(obj.get_files())
        return [file.id for file in files]
        """ serializer = FileSerializer(files, many=True)
        return serializer.data """
    class Meta:
        model = models.Album
        fields = ("id", "name", "file_count", "files")


# Serializer for album-file relationship TODO
class AlbumFileSerializer(serializers.ModelSerializer):
    def create(self, validated_data):
        if not validated_data["album"].get_file_rels().filter(file=validated_data["file"]).exists():
            models.AlbumFile(album=validated_data["album"], file=validated_data["file"]).save()
            validated_data["album"].remove_from_parents(validated_data["file"])
        return validated_data

    class Meta:
        model = models.AlbumFile
        fields = ("id", "file", "album")


class PersonGroupSerializer(serializers.ModelSerializer):
    """ PersonGroup model serializer

    Only provides name of group.
    """
    """ person_count = serializers.SerializerMethodField()
    people = serializers.SerializerMethodField()

    def get_person_count(self, obj):
        return models.Person.objects.filter(group=obj).count()

    def get_people(self, obj):
        people = models.Person.objects.filter(group=obj)
        serializer = RootPersonSerializer(people, many=True)
        return serializer.data """
    class Meta:
        model = models.PersonGroup
        fields = ("id", "name")  # , "person_count", "people")


class PersonListSerializer(serializers.ModelSerializer):
    """ Person model serializer, for list view

    Provides data about person, but not associated faces.
    """

    face_count = serializers.SerializerMethodField()
    thumbnail = serializers.SerializerMethodField()

    def get_face_count(self, obj):
        return models.Face.objects.filter(person=obj, status__lt=4).count()

    def get_thumbnail(self, obj):
        return obj.thumbnail.id if obj.thumbnail is not None else None

    class Meta:
        model = models.Person
        fields = ("id", "full_name", "face_count", "thumbnail", "group")  # TODO only display group when in /api/people/


class PersonSerializer(PersonListSerializer):
    """ Person model serializer, for retrieve view

    Provides data about person and associated face IDs.
    """

    # faces = serializers.SerializerMethodField()

    def get_faces(self, obj):
        faces = self.extract_files(models.Face.objects.filter(person=obj, status__lt=4), paginate=False)
        # TODO not sure about self.extract_files here
        return [face.id for face in faces]
        """ serializer = FaceSerializer(faces, many=True)
        return serializer.data """
    class Meta:
        model = models.Person
        fields = PersonListSerializer.Meta.fields  # + ("faces",)


class FaceSerializer(serializers.ModelSerializer):
    """ Face model serializer

    Provides data for file, and ID for person.
    """

    file = FileSerializer()

    class Meta:
        model = models.Face
        fields = ("id", "rect_x", "rect_y", "rect_w", "rect_h", "file", "person", "status")
        extra_kwargs = {field: {"read_only": True} for field in fields if field not in ["person", "status"]}


class GeoTagAreaSerializer(serializers.ModelSerializer):
    """ GeoTagArea model serializer """
    class Meta:
        model = models.GeoTagArea
        fields = ("id", "name", "address", "latitude", "longitude", "radius")
