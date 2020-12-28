# Standard imports
import datetime
import functools
import io
import json
import math
import operator
import os
import traceback

# Django imports
from django.db import models
from simple_history.models import HistoricalRecords

# Third-party imports
import cv2
import exifread
import mutagen
import numpy
import piexif
from PIL import Image
import face_recognition
from sklearn import neighbors

# Local imports
from . import scancrop, utils
from .membership.models import *

# Allow very large images to be read
Image.MAX_IMAGE_PIXELS = None

# Global Haar cascades dict
cascades = None


# Override default display name for models
def default_str(self):
    return self.name if hasattr(self, "name") else self.id


models.Model.__str__ = default_str


# Base class for Folder and ScanFolder models
class BaseFolder(models.Model):
    class Meta:
        abstract = True

    # List filenames from local filesystem
    def get_fs_filenames(self):
        return os.listdir(self.get_real_path())

    # Scan system for new files
    def scan_filesystem(self):
        utils.log("Scanning folder: %s" % self.name)
        real_path = self.get_real_path()
        files = self.get_fs_filenames()
        for filename in files:
            if os.path.isdir(real_path + filename):
                self.folder_cls().from_fs(filename, self)
            else:
                self.file_cls().from_fs(filename, self)

    # Clear deleted files from database
    def prune_database(self):
        utils.log("Pruning database of folder: %s" % self.name)

        # Prune subfolders
        folders = self.folder_cls().objects.filter(parent=self)
        for folder in folders:
            folder.prune_database()

        # Prune top-level files
        files = self.file_cls().objects.filter(folder=self)
        for file in files:
            if not os.path.isfile(file.get_real_path()):
                utils.log("Clearing file from database: %s/%s" % (self.name, file.name))
                file.delete()

        # Delete self if needed
        if not os.path.isdir(self.get_real_path()):
            self.delete()

    # Recursively update cached properties (when database updated)
    def update_props(self):
        # Update path
        if self.parent is None:
            self.path = self.name.rstrip("/") + "/"
        else:
            self.path = self.parent.path + self.name.strip("/") + "/"
        self.save()

        # Recursively update subfolders
        subfolders = self.folder_cls().objects.filter(parent=self)
        for folder in subfolders:
            folder.update_props()
        files = self.file_cls().objects.filter(folder=self)

        # Update file count
        subfolder_count = sum([folder.file_count for folder in subfolders])
        file_count = files.count()
        self.file_count = subfolder_count + file_count

        # Update length
        if self.has_length:
            subfolder_length = sum(folder.length for folder in subfolders)
            file_length = files.aggregate(models.Sum("length"))["length__sum"] or 0
            self.length = subfolder_length + file_length

        self.save()

    # Add folder to database from filesystem
    @classmethod
    def from_fs(cls, name, parent):
        # Create folder if needed
        folder_qs = cls.objects.filter(name=name, parent=parent)
        if folder_qs.exists():
            folder = folder_qs.first()
        else:
            folder = cls.objects.create(name=name, parent=parent)

        # Recursively load folder contents
        folder.scan_filesystem()

        return folder

    # Full local filesystem path to folder
    def get_real_path(self):
        if self.parent is None:
            return self.root_folder_cls().objects.filter(folder=self).first().get_real_path()
        else:
            return self.parent.get_real_path() + self.name.strip("/") + "/"

    # Get child folders
    def get_children(self, include_subfolders):
        children = self.folder_cls().objects.filter(parent=self)
        if include_subfolders:
            return functools.reduce(operator.or_, (child.get_children(True) for child in children), children)
        else:
            return children

    # Get files
    def get_files(self, include_subfolders=False, queryset=None):
        if queryset is None:
            queryset = self.file_cls().objects

        files = queryset.filter(folder=self)
        if include_subfolders:
            return functools.reduce(operator.or_, (child.get_files() for child in self.get_children(True)), files)
        else:
            return files


# Model for representing folders in virtual filesystem
class Folder(BaseFolder):
    # Class information for BaseFolder methods
    root_folder_cls = lambda s: RootFolder
    folder_cls = lambda s: Folder
    file_cls = lambda s: File
    has_length = True

    history = HistoricalRecords()

    name = models.TextField()
    parent = models.ForeignKey("Folder", on_delete=models.CASCADE, related_name="+", null=True, blank=True)
    file_count = models.PositiveIntegerField(default=0)
    length = models.PositiveBigIntegerField(default=0)
    path = models.TextField(default="")

    # Detect faces in files in folder
    def detect_faces(self):
        utils.log("Detecting faces in folder: %s" % self.name)

        # Load cascades if needed
        global cascades
        if cascades is None:
            cascades = {}
            cascades["face"] = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_alt.xml")
            cascades["eye"] = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")
            cascades["left_eye"] = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_lefteye_2splits.xml")
            cascades["right_eye"] = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_righteye_2splits.xml")

        # Detect faces in subfolders
        folders = Folder.objects.filter(parent=self)
        for folder in folders:
            folder.detect_faces()

        # Detect faces in top-level files
        files = File.objects.filter(folder=self)
        for file in files:
            file.detect_faces()


# Model for representing root folders
class RootFolder(models.Model):
    history = HistoricalRecords()

    name = models.TextField()
    real_path = models.TextField()
    folder = models.OneToOneField("Folder", on_delete=models.CASCADE, related_name="+", null=True, blank=True)

    # Create an attached Folder model upon creation
    @classmethod
    def post_create(cls, sender, instance, created, *args, **kwargs):
        if created:
            instance.folder = Folder.objects.create(name=instance.name)
            instance.save()

    # Full local filesystem path to folder
    def get_real_path(self):
        return self.real_path.rstrip("/") + "/"

    # Scan local filesystem for new files and remove deleted files
    def scan_filesystem(self):
        self.folder.scan_filesystem()
        self.folder.prune_database()
        self.folder.update_props()

    # Detect faces in contained files
    def detect_faces(self):
        self.folder.detect_faces()

    # Update all aspects of the database
    def update_database(self):
        try:
            self.scan_filesystem()
            self.detect_faces()
            Face.recognize_faces()
        except Exception:
            utils.log(traceback.format_exc())


# Attach method to run when RootFolder instances are created
models.signals.post_save.connect(RootFolder.post_create, sender=RootFolder)


# Album model into which files can be sorted (files can be added to multiple albums)
class Album(models.Model):
    history = HistoricalRecords()

    name = models.TextField()
    parent = models.ForeignKey("Album", on_delete=models.CASCADE, related_name="+", null=True, blank=True)
    files = models.ManyToManyField("File", through="AlbumFile")
    date_created = models.DateTimeField(auto_now_add=True)

    # Display name (path)
    def __str__(self):
        return self.path

    # Path of album (found recursively)
    @property
    def path(self):
        if self.parent is None:
            return self.name + "/"
        else:
            return self.parent.path + self.name + "/"

    # File count in album (including children)
    @property
    def file_count(self):
        return self.get_files().count()

    # Get child albums
    def get_children(self, recurse=False):
        children = Album.objects.filter(parent=self)
        if recurse:
            return functools.reduce(operator.or_, (child.get_children(True) for child in children), children)
        else:
            return children

    # Get files in album (including children)
    def get_files(self):
        all_files = self.files.all()
        return functools.reduce(operator.or_, (child.files.all() for child in self.get_children(True)), all_files)

    # Get AlbumFile relationships for album and its children
    def get_file_rels(self):
        album_files = AlbumFile.objects.filter(album=self)
        return functools.reduce(operator.or_, (AlbumFile.objects.filter(album=child) for child in self.get_children(True)), album_files)

    # Remove file from parent albums (before adding to this album, to avoid duplication)
    def remove_from_parents(self, to_remove):
        if self.parent is not None:
            album_file_qs = AlbumFile.objects.filter(album=self.parent, file=to_remove)
            album_file_qs.delete()
            self.parent.remove_from_parents(to_remove)


# Album-File relationship
class AlbumFile(models.Model):
    history = HistoricalRecords()

    album = models.ForeignKey(Album, on_delete=models.CASCADE, related_name="+")
    file = models.ForeignKey("File", on_delete=models.CASCADE, related_name="+")
    date_added = models.DateTimeField(auto_now_add=True)

    # Display name (album and file)
    def __str__(self):
        return str(self.album) + " - " + str(self.file)


# Main file model (for all formats)
class File(models.Model):
    history = HistoricalRecords()

    FILE_TYPES = (("image", "Image file"), ("video", "Video file"), ("file", "Non-image file"))

    file_id = models.CharField(max_length=24)
    name = models.TextField(null=True)
    folder = models.ForeignKey("Folder", on_delete=models.CASCADE, related_name="+")
    type = models.TextField(choices=FILE_TYPES, default="file")
    format = models.TextField(null=True)
    length = models.PositiveBigIntegerField()
    is_starred = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    notes = models.TextField(null=True)
    timestamp = models.DateTimeField(null=True)
    scanned_faces = models.BooleanField(default=False)

    width = models.PositiveIntegerField(null=True)
    height = models.PositiveIntegerField(null=True)
    orientation = models.PositiveIntegerField(default=1)
    duration = models.DurationField(null=True)
    geotag = models.OneToOneField("GeoTag", on_delete=models.SET_NULL, null=True, blank=True)
    metadata = models.TextField(default="{}")
    # TODO get video details using ffmpeg https://gist.github.com/oldo/dc7ee7f28851922cca09

    # File format-type dict
    types = {"image": ["jpg", "jpeg", "png"], "video": ["mp4", "mov"]}

    # Add file to database from local filesystem (detects existing/moved files, but not edited files)
    @staticmethod
    def from_fs(full_name, folder):
        utils.log("Found file: %s/%s" % (folder.name, full_name))

        # Get file name/path
        name, extension = os.path.splitext(full_name)
        real_path = folder.get_real_path() + full_name

        # Search for file already in database
        file_qs = File.objects.filter(file_id=name)
        if file_qs.exists():
            file = file_qs.first()
            if not os.path.isfile(file.get_real_path()):
                file.folder = folder
                file.save()

            if file.folder == folder:
                return file

        utils.log("Adding file to database: %s/%s" % (folder.name, full_name))

        # Create new file dictionary
        new_file = {"folder": folder, "type": File.get_type(extension), "format": extension[1:]}

        # Get EXIF and mutagen data from file
        exif_data = File.get_exif(real_path)
        mutagen_data = mutagen.File(real_path, easy=True) or {}

        # Get file title from exif or name
        exif_title = utils.get_if_exist(exif_data, ["Image", "ImageDescription"])
        mutagen_title = utils.get_if_exist(mutagen_data, ["title"]) or utils.get_if_exist(mutagen_data, ["©nam"])
        if exif_title and exif_title.strip():
            new_file["name"] = exif_title.strip()
            write_title = False
        elif mutagen_title:
            if isinstance(mutagen_title, list):
                mutagen_title = ", ".join(mutagen_title)

            new_file["name"] = mutagen_title
            write_title = False
        else:
            new_file["name"] = name
            write_title = True

        # Get file size
        new_file["length"] = os.path.getsize(real_path)

        # Get file timestamp
        new_file["timestamp"] = None
        all_timestamps = []
        for exif_timestamp in [
                utils.get_if_exist(exif_data, ["EXIF", "DateTimeOriginal"]),
                utils.get_if_exist(exif_data, ["Image", "DateTime"]),
                utils.get_if_exist(exif_data, ["EXIF", "DateTimeDigitized"])
        ]:
            try:
                all_timestamps.append(datetime.datetime.strptime(exif_timestamp, "%Y:%m:%d %H:%M:%S"))
            except (ValueError, TypeError):
                all_timestamps.append(None)

        # Choose best available timestamp
        if all_timestamps[0] is not None:
            new_file["timestamp"] = all_timestamps[0]
        elif all_timestamps[1] is not None and all_timestamps[2] is not None:
            new_file["timestamp"] = min(all_timestamps[1], all_timestamps[2])
        elif all_timestamps[1] is not None:
            new_file["timestamp"] = all_timestamps[1]
        elif all_timestamps[2] is not None:
            new_file["timestamp"] = all_timestamps[2]
        else:
            id_timestamp = File.get_id_date(name)
            if id_timestamp is not None:
                new_file["timestamp"] = id_timestamp
            else:
                new_file["timestamp"] = datetime.datetime.fromtimestamp(os.path.getmtime(real_path))

        # Get image dimensions
        exif_width = utils.get_if_exist(exif_data, ["EXIF", "ExifImageWidth"])
        exif_height = utils.get_if_exist(exif_data, ["EXIF", "ExifImageLength"])
        if exif_width and exif_height:
            new_file["width"] = exif_width
            new_file["height"] = exif_height
        elif new_file["type"] == "image":
            image = Image.open(real_path)
            new_file["width"] = image.size[0]
            new_file["height"] = image.size[1]
            image.close()

        # Extract EXIF orientation
        new_file["orientation"] = utils.get_if_exist(exif_data, ["Image", "Orientation"]) or 1

        exif_geotag = GeoTag.from_exif(exif_data)
        if exif_geotag:
            new_file["geotag"] = exif_geotag
        # TODO get from other metadata if possible

        # Assign metadata dictionary to new file
        all_metadata = {"path": folder.path + name, "mtime": os.path.getmtime(real_path), "exif": exif_data, "mutagen": mutagen_data}
        new_file["metadata"] = json.dumps(all_metadata, default=lambda obj: str(obj) if isinstance(obj, bytes) else obj.__dict__)

        # Generate ID for file
        new_file["file_id"] = File.get_id_name(new_file)

        # Create new file object
        file = File.objects.create(**new_file)

        # Get full path of new filename
        new_real_path = folder.get_real_path() + new_file["file_id"] + extension

        # Rename file
        os.rename(real_path, new_real_path)

        # Write file title to EXIF (or other metadata format)
        if write_title:
            try:
                exif_dict = piexif.load(new_real_path)
                exif_dict["0th"][piexif.ImageIFD.ImageDescription] = new_file["name"]
                piexif.insert(piexif.dump(exif_dict), new_real_path)
            except Exception:
                mutagen_file = mutagen.File(new_real_path, easy=True)
                if mutagen_file is not None:
                    mutagen_file["title"] = new_file["name"]
                    mutagen_file.save()

        return file

    # Get the file type (image/video/other) from extension
    @staticmethod
    def get_type(extension):
        if not extension:
            return "file"

        extension = extension[1:].lower()
        for file_type in File.types:
            if extension in File.types[file_type]:
                return file_type

        return "file"

    # Read exif data from local filesystem to a dictionary
    @staticmethod
    def get_exif(real_path):
        file = open(real_path, "rb")
        exif = exifread.process_file(file)
        file.close()
        exif_data = {}

        for tag in exif:
            if tag == "JPEGThumbnail" or tag == "EXIF MakerNote":
                continue

            ifd = tag[:tag.find(" ")]
            if ifd not in exif_data:
                exif_data[ifd] = {}

            if exif[tag].field_type in [3, 4, 5] and isinstance(exif[tag].values, list) and len(exif[tag].values) == 1:
                exif_data[ifd][tag[tag.find(" ") + 1:]] = exif[tag].values[0]
            else:
                exif_data[ifd][tag[tag.find(" ") + 1:]] = exif[tag].values

        return exif_data

    # Generate unique file ID from timestamp
    @staticmethod
    def get_id_name(file):
        dt_id = file["timestamp"].strftime("%Y-%m-%d_%H-%M-%S")

        file_qs = File.objects.filter(file_id__startswith=dt_id).order_by("file_id")
        if file_qs.exists():
            max_id = int(file_qs.last().file_id[20:], 16)
        else:
            max_id = 0

        return dt_id + "_" + "%04x" % (max_id + 1)

    # Display name (name, file_id, format)
    def __str__(self):
        return "%s (%s.%s)" % (self.name, self.file_id, self.format)

    # All albums (including parents) to which file belongs (unused)
    @property
    def albums(self):
        all_albums = set()
        for album_file in AlbumFile.objects.filter(file=self):
            album = album_file.album
            all_albums.add(album)
            while album.parent is not None:
                album = album.parent
                all_albums.add(album)

        return list(all_albums)

    # Faces found in file (unused)
    @property
    def faces(self):
        return Face.objects.filter(file=self)

    # Full (virtual) path to file (including filename)
    @property
    def path(self):
        return self.folder.path + self.name  # self.file_id + "." + self.format

    # Get full local filesystem file path
    def get_real_path(self):
        return self.folder.get_real_path() + self.file_id + "." + self.format

    # Get file timestamp from file_id (None if malformatted)
    @staticmethod
    def get_id_date(file_id):
        try:
            return datetime.datetime.strptime(file_id[:-5], "%Y-%m-%d_%H-%M-%S")
        except ValueError:
            return None

    # Detect faces in (image) file (using OpenCV Haar Cascades, attempting to find eye locations also)
    def detect_faces(self):
        # Return if file is not an image, or if it has already been scanned
        if self.type != "image" or self.scanned_faces:
            return

        # Use globally stored Haar cascades
        global cascades

        # Local config
        config = {"max_size": 1000}

        utils.log("Detecting faces in file: %s" % str(self))

        # Load the image, convert it to grayscale and scale it down to minimise false positives
        full_image = cv2.imread(self.get_real_path())
        height, width = full_image.shape[:2]
        ratio = config["max_size"] / max(width, height)
        if ratio > 1:
            ratio = 1
        scaled_image = cv2.resize(full_image, (round(width * ratio), round(height * ratio)))
        grayscale = cv2.cvtColor(scaled_image, cv2.COLOR_BGR2GRAY)
        full_grayscale = cv2.cvtColor(full_image, cv2.COLOR_BGR2GRAY)

        # Run the detection algorithm
        faces = cascades["face"].detectMultiScale(grayscale, 1.1, 5, 0, (round(config["max_size"] / 50), round(config["max_size"] / 50)))

        for x, y, w, h in faces:
            # Get face image data
            face_mat = full_grayscale[int(round(y / ratio)):int(round((y + h) / ratio)), int(round(x / ratio)):int(round((x + w) / ratio))]

            # Attempt to find eyes in face
            eyes = Face.get_eyes(face_mat)

            # Get rotation from eyes (or set defaults)
            if eyes is None:
                eyes_found = False
                rotation = 0
                eyes = ((0, -h / (8 * 1.625)), (0, -h / (8 * 1.625)))
            else:
                eyes_found = True
                rotation = Face.get_rotation(eyes)

                # Cut off rotation at 45 degrees, on the assumption that faces should not be sideways
                # NOTE this is not ideal but there are too many false-positives for eyes
                if abs(rotation) > 45:
                    rotation = 0

            # Face data
            # TODO center is shifted vertically upwards - maybe should be in line with rotation
            face_dict = {
                "rect_x": (x + w / 2) / ratio,
                "rect_y": (y + h * 3 / 8) / ratio,
                "rect_w": w * 1.3 / ratio,
                "rect_h": h * 1.625 / ratio,
                "eyes_found": eyes_found,
                "rect_r": rotation,
                # TODO pretty sure below are wrong - need to fix before release but not urgent enough right now
                "eye_l_x": eyes[0][0] * 1.3 / ratio,
                "eye_l_y": (eyes[0][1] * 1.625 + h / 8) / ratio,
                "eye_r_x": eyes[1][0] * 1.3 / ratio,
                "eye_r_y": (eyes[1][1] * 1.625 + h / 8) / ratio,
                "file": self,
                "uncertainty": -1,
                "status": 3
            }

            face = Face.objects.create(**face_dict)
            face.save_thumbnail()

        # Register that file has now been scanned
        self.scanned_faces = True
        self.save()

        utils.log("Detected %s faces in file: %s" % (len(faces), str(self)))


# Category model for people
class PersonGroup(models.Model):
    history = HistoricalRecords()

    name = models.TextField()


# Person model to identify faces found in files
class Person(models.Model):
    history = HistoricalRecords()

    full_name = models.TextField()
    group = models.ForeignKey(PersonGroup, on_delete=models.SET_DEFAULT, default=0, related_name="+")
    date_created = models.DateTimeField(auto_now_add=True)

    # Select largest confirmed face to use as thumbnail (None if no confirmed faces)
    @property
    def thumbnail(self):
        face_set = Face.objects.filter(person=self, status__lt=2).order_by("-rect_w")

        if self.id != 0 and face_set.exists():
            return face_set.first()
        else:
            return None

    # Display name (name and group)
    def __str__(self):
        return "%s (%s)" % (self.full_name, str(self.group))

    # Get all faces (confirmed and unconfirmed)
    def get_faces(self):
        return Face.objects.filter(person=self, status__lt=4)


# Update person/status fields on Face model when associated Person object is deleted
def face_on_person_delete():
    def on_person_delete(collector, field, sub_objs, using):
        collector.add_field_update(field, field.get_default(), sub_objs)
        collector.add_field_update(sub_objs[0]._meta.get_field("status"), 3, sub_objs)

    on_person_delete.deconstruct = lambda: ('fileserver.models.face_on_person_delete', (), {})

    return on_person_delete


# Face model for faces found in image files
class Face(models.Model):
    history = HistoricalRecords()

    STATUS_OPTIONS = ((0, "Confirmed (root)"), (1, "Confirmed (user)"), (2, "Predicted"), (3, "Unassigned"), (4, "Ignored"), (5, "Removed"))

    rect_x = models.PositiveIntegerField()
    rect_y = models.PositiveIntegerField()
    rect_w = models.PositiveIntegerField()
    rect_h = models.PositiveIntegerField()
    rect_r = models.FloatField()

    eyes_found = models.BooleanField()
    eye_l_x = models.PositiveIntegerField()
    eye_l_y = models.PositiveIntegerField()
    eye_r_x = models.PositiveIntegerField()
    eye_r_y = models.PositiveIntegerField()

    file = models.ForeignKey(File, on_delete=models.CASCADE, related_name="+")
    person = models.ForeignKey(Person, on_delete=face_on_person_delete(), default=0, related_name="+")
    uncertainty = models.FloatField()
    status = models.PositiveIntegerField(choices=STATUS_OPTIONS)

    thumbnail = models.BinaryField(null=True)

    # Detect eyes (format [(l_x, l_y), (r_x, r_y)] or None) in face (given as OpenCV pixel matrix)
    @staticmethod
    def get_eyes(face):
        global cascades

        height, width = face.shape[:2]

        # Detect all possible eyes
        both_eyes = [(e[0] + e[2] / 2, e[1] + e[3] / 2)
                     for e in cascades["eye"].detectMultiScale(face, 1.1, 5, 0, (round(width / 6), round(height / 6)), (round(width / 4), round(height / 4)))]
        left_eyes = [(e[0] + e[2] / 2, e[1] + e[3] / 2)
                     for e in cascades["left_eye"].detectMultiScale(face, 1.1, 5, 0, (round(width / 7), round(height / 7)), (round(width / 3), round(height / 3)))]
        right_eyes = [(e[0] + e[2] / 2, e[1] + e[3] / 2)
                      for e in cascades["right_eye"].detectMultiScale(face, 1.1, 5, 0, (round(width / 7), round(height / 7)), (round(width / 3), round(height / 3)))]

        # Sort eyes by position
        both_eyes.sort(key=lambda eye: eye[1])
        left_eyes.sort(key=lambda eye: eye[1])
        right_eyes.sort(key=lambda eye: eye[1])

        # Choose eyes
        left_eye = Face.choose_eye(left_eyes + both_eyes + right_eyes, False, width, height)
        right_eye = Face.choose_eye(right_eyes + both_eyes + left_eyes, True, width, height)

        # Return result
        if left_eye is None or right_eye is None:
            return None
        else:
            return [left_eye, right_eye]

    # Choose best eye (or None) from list for one side (left = False, right = True) of a face of given dimensions
    @staticmethod
    def choose_eye(all_eyes, side, width, height):
        for eye in all_eyes:
            eye_side = Face.get_eye_side(eye, width, height)
            if eye_side == side:
                return eye

        return None

    # Determine which side (left = False, right = True) of the face an eye (given as (x, y)) is on
    # (top-left/bottom-right => left, top-right/bottom-left => right to detect upside down faces)
    @staticmethod
    def get_eye_side(eye, width, height):
        x = eye[0] - width / 2
        y = height / 2 - eye[1]

        return y / x < 0

    # Get angle of rotation (degrees) of face from eye positions (format [(l_x, l_y), (r_x, r_y)])
    @staticmethod
    def get_rotation(eyes):
        x_diff = eyes[0][0] - eyes[1][0]
        y_diff = eyes[0][1] - eyes[1][1]

        return math.degrees(math.atan(y_diff / x_diff))

    # Attempt to identify all unconfirmed faces in database, based on user-confirmed faces
    @staticmethod
    def recognize_faces():
        utils.log("Recognising faces found previously")

        # Settings
        n_neighbors = None  # Chosen automatically
        knn_algo = "ball_tree"
        distance_threshold = 0.5

        # Add each known face
        utils.log("Encoding known faces")
        faces_done = 0
        faces_skipped = 0
        X = []
        y = []
        for person in Person.objects.all():
            faces = Face.objects.filter(person__id=person.id, status__lt=2)
            utils.log(f"Encoding {faces.count()} faces for {person.full_name}")
            for face in faces:
                image = face.get_image(cv2.COLOR_BGR2RGB)
                face_bounding_boxes = face_recognition.face_locations(image)
                if len(face_bounding_boxes) != 1:
                    # Skip face if face_locations cannot properly detect it
                    faces_skipped += 1
                else:
                    # Add face encoding for current image to the training set
                    X.append(face_recognition.face_encodings(image, known_face_locations=face_bounding_boxes)[0])
                    y.append(person.id)
                    faces_done += 1
        utils.log(f"Encoded {faces_done} faces, skipped {faces_skipped} faces")

        if faces_done == 0:
            utils.log("No faces identified, skipping recognition.")
            return

        # Determine how many neighbors to use for weighting in the KNN classifier
        if n_neighbors is None:
            n_neighbors = int(round(math.sqrt(len(X))))

        utils.log("Training KNN classifier")

        # Create and train the KNN classifier
        knn_clf = neighbors.KNeighborsClassifier(n_neighbors=n_neighbors, algorithm=knn_algo, weights='distance')
        knn_clf.fit(X, y)

        utils.log("Trained classifier")

        # Fetch unconfirmed faces
        unknown_faces = Face.objects.filter(status__lt=4, status__gt=1)
        utils.log("Unidentified faces: %s" % len(unknown_faces))

        # Predict identities of unknown faces, and save to database
        utils.log("Predicting face identities")
        faces_skipped = 0
        faces_done = 0
        faces_unknown = 0
        for face in unknown_faces:
            X_img = face.get_image(cv2.COLOR_BGR2RGB)
            X_face_locations = face_recognition.face_locations(X_img)

            # Skip face if face_locations cannot properly detect it
            if len(X_face_locations) != 1:
                faces_skipped += 1
                face.person = Person.objects.filter(id=0).first()
                face.status = 3
                face.save()
            else:
                faces_encodings = face_recognition.face_encodings(X_img, known_face_locations=X_face_locations)

                closest_distances = knn_clf.kneighbors(faces_encodings, n_neighbors=1)
                is_match = closest_distances[0][0][0] <= distance_threshold

                result = knn_clf.predict(faces_encodings)[0] if is_match else 0
                utils.log("Predicted %s with confidence %s" % (Person.objects.filter(id=result).first().full_name, closest_distances[0][0][0]))
                if result != 0:
                    faces_done += 1
                    face.status = 2
                else:
                    faces_unknown += 1
                face.person = Person.objects.filter(id=result).first()
                face.uncertainty = closest_distances[0][0][0]
                face.save()

        utils.log(f"Predicted {faces_done} face identities, failed to identify {faces_unknown} faces, skipped {faces_skipped} faces")

    # Display name (person, id, file)
    def __str__(self):
        return f"{self.person.full_name} ({self.id}) in {self.file}"

    # Get image data (as OpenCV pixel matrix) for face (with given OpenCV colour encoding and height options)
    def get_image(self, color, **kwargs):
        x = self.rect_x
        y = self.rect_y
        w = self.rect_w
        h = self.rect_h
        r = self.rect_r

        if "height" in kwargs:
            height = kwargs["height"]
        else:
            height = h

        full_image = cv2.cvtColor(cv2.imread(self.file.get_real_path()), color)

        # Define custom rounding function
        def cround(n):
            return math.ceil(n) if n % 1 >= 0.5 else math.floor(n)

        # Crop down to bbox

        # Magnitude and direction of bbox diagonal
        diagonal = math.sqrt(w**2 + h**2)
        diag_angle = math.atan(h / w)
        # Intended (non-rounded) bbox size
        bbox_h = max(diagonal * abs(math.sin(-diag_angle - abs(math.radians(r)))), h)
        bbox_w = max(diagonal * abs(math.cos(diag_angle - abs(math.radians(r)))), w)
        # Actual size of final bbox
        bbox_h_rounded = cround(y + bbox_h / 2) - cround(y - bbox_h / 2)
        bbox_w_rounded = cround(x + bbox_w / 2) - cround(x - bbox_w / 2)
        bbox_image = numpy.zeros(shape=(bbox_h_rounded, bbox_w_rounded) + (() if color == cv2.COLOR_BGR2GRAY else (3, )), dtype=numpy.uint8)
        # Co-ordinates and dimensions of box to copy from original image
        virtual_y1, virtual_y2, virtual_x1, virtual_x2 = cround(y - bbox_h / 2), cround(y + bbox_h / 2), cround(x - bbox_w / 2), cround(x + bbox_w / 2)
        actual_y1, actual_y2, actual_x1, actual_x2 = max(virtual_y1, 0), min(virtual_y2, full_image.shape[0]), max(virtual_x1, 0), min(virtual_x2, full_image.shape[1])
        bbox_copy_h, bbox_copy_w = actual_y2 - actual_y1, actual_x2 - actual_x1
        # Co-ordinate region to copy to in bbox
        bbox_y1, bbox_x1 = -min(virtual_y1, 0), -min(virtual_x1, 0)
        bbox_y2, bbox_x2 = bbox_y1 + bbox_copy_h, bbox_x1 + bbox_copy_w
        # Copy pixels
        bbox_image[bbox_y1:bbox_y2, bbox_x1:bbox_x2] = full_image[actual_y1:actual_y2, actual_x1:actual_x2]

        x = bbox_w / 2
        y = bbox_h / 2

        # Scale down image to desired size
        if height != h:
            scale = height / h
            scaled_image = cv2.resize(bbox_image, (cround(bbox_w * scale), cround(bbox_h * scale)))
            x *= scale
            y *= scale
            w *= scale
            h *= scale
            bbox_w *= scale
            bbox_h *= scale
        else:
            scaled_image = bbox_image

        # Rotate image
        M = cv2.getRotationMatrix2D((x, y), r, 1)
        rot_image = cv2.warpAffine(scaled_image, M, (cround(bbox_w), cround(bbox_h)))

        # Crop down to face
        face_image = rot_image[cround(y - h / 2):cround(y + h / 2), cround(x - w / 2):cround(x + w / 2)]

        return face_image

    # Extract face thumbnail from image file (local filesystem) and save to database
    def save_thumbnail(self):
        face_thumb = self.get_image(cv2.COLOR_BGR2RGB, height=200)
        pil_thumb = Image.fromarray(face_thumb)
        stream = io.BytesIO()
        pil_thumb.save(stream, "JPEG", quality=75)
        self.thumbnail = stream.getvalue()
        self.save()


# Geotag area model for grouping geotags of multiple files associated with the same location/area
class GeoTagArea(models.Model):
    history = HistoricalRecords()

    name = models.TextField()
    address = models.TextField()
    latitude = models.FloatField()
    longitude = models.FloatField()
    radius = models.FloatField()
    date_created = models.DateTimeField(auto_now_add=True)


# Geotag model for storing image file locations
class GeoTag(models.Model):
    history = HistoricalRecords()

    latitude = models.FloatField(null=True)
    longitude = models.FloatField(null=True)
    area = models.ForeignKey(GeoTagArea, on_delete=models.CASCADE, related_name="+", null=True)
    # created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+", null=True)
    date_created = models.DateTimeField(auto_now_add=True)

    # Display name (lat, lng, area)
    def __str__(self):
        return "%s, %s (%s)" % (round(self.latitude, 2) if self.latitude is not None else None, round(self.longitude, 2) if self.longitude is not None else None, self.area)

    # Convert EXIF GPS co-ordinates ([degrees, arcminutes, arcseconds] each in format { num : str, den : str }) to a single value (degrees)
    @staticmethod
    def exif_to_degrees(values):
        d = float(values[0].num) / float(values[0].den)
        m = float(values[1].num) / float(values[1].den)
        s = float(values[2].num) / float(values[2].den)

        return d + (m / 60.0) + (s / 3600.0)

    # Create new GeoTag instance (or None) from location information stored in EXIF data
    @staticmethod
    def from_exif(exif_data):
        # Extract variables from dict
        exif_latitude = utils.get_if_exist(exif_data, ["GPS", "GPSLatitude"])
        exif_latitude_ref = utils.get_if_exist(exif_data, ["GPS", "GPSLatitudeRef"])
        exif_longitude = utils.get_if_exist(exif_data, ["GPS", "GPSLongitude"])
        exif_longitude_ref = utils.get_if_exist(exif_data, ["GPS", "GPSLongitudeRef"])

        # Extract data from variables
        if exif_latitude and exif_latitude_ref and exif_longitude and exif_longitude_ref:
            latitude = GeoTag.exif_to_degrees(exif_latitude)
            if exif_latitude_ref[0] != "N":
                latitude = 0 - latitude

            longitude = GeoTag.exif_to_degrees(exif_longitude)
            if exif_longitude_ref[0] != "E":
                longitude = 0 - longitude

            return GeoTag.objects.create(latitude=latitude, longitude=longitude)
        else:
            return None


# Root Folder for Scan files
class ScanRootFolder(models.Model):
    history = HistoricalRecords()

    name = models.TextField()
    real_path = models.TextField()
    output_folder = models.ForeignKey(Folder, on_delete=models.PROTECT, related_name="+")
    folder = models.OneToOneField("ScanFolder", on_delete=models.CASCADE, related_name="+", null=True, blank=True)

    # Create attached ScanFolder model when created
    @classmethod
    def post_create(cls, sender, instance, created, *args, **kwargs):
        if created:
            instance.folder = ScanFolder.objects.create(name=instance.name)
            instance.save()

    # Get full local filesystem path to folder
    def get_real_path(self):
        return self.real_path.rstrip("/") + "/"

    # Update database to reflect local filesystem
    def update_database(self):
        try:
            self.folder.scan_filesystem()
            self.folder.prune_database()
            self.folder.update_props()
            self.folder.generate_output_tree(self.output_folder)
        except Exception:
            utils.log(traceback.format_exc())


# Attach method to run when ScanRootFolder instances are created
models.signals.post_save.connect(ScanRootFolder.post_create, sender=ScanRootFolder)


# Folder for Scan files
class ScanFolder(BaseFolder):
    # Class information for BaseFolder methods
    root_folder_cls = lambda s: ScanRootFolder
    folder_cls = lambda s: ScanFolder
    file_cls = lambda s: Scan
    has_length = False

    history = HistoricalRecords()

    name = models.TextField()
    output_folder = models.ForeignKey(Folder, on_delete=models.PROTECT, related_name="+", null=True, blank=True)
    parent = models.ForeignKey("ScanFolder", on_delete=models.CASCADE, related_name="+", null=True, blank=True)
    file_count = models.PositiveIntegerField(default=0)
    path = models.TextField(default="")

    # Generate all output folders
    def generate_output_tree(self, output_folder):
        self.output_folder = output_folder
        self.save()
        for child in ScanFolder.objects.filter(parent=self):
            output_path = output_folder.get_real_path() + child.name.strip("/") + "/"
            if not os.path.isdir(output_path):
                os.mkdir(output_path)
            new_folder = Folder.from_fs(child.name.strip(), output_folder)
            child.generate_output_tree(new_folder)


# Scan model for scanned photograph image files
class Scan(models.Model):
    history = HistoricalRecords()

    name = models.TextField(null=True)
    format = models.TextField(null=True)
    folder = models.ForeignKey("ScanFolder", on_delete=models.CASCADE, related_name="+")
    done_output = models.BooleanField(default=False)

    width = models.PositiveIntegerField(null=True)
    height = models.PositiveIntegerField(null=True)
    orientation = models.PositiveIntegerField(null=True)

    # Get full local filesystem file path
    def get_real_path(self):
        return self.folder.get_real_path() + self.name + "." + self.format

    # Get (real) path to save cropped photos
    def get_output_path(self):
        return self.folder.output_folder.get_real_path() + self.name

    # Get locations of photos given crop lines
    def get_image_rects(self, lines, options):
        return scancrop.get_image_rects(self.get_real_path(), lines, self.width, self.height, options)

    # Save cropped images given crop lines
    def confirm_crop(self, lines, options):
        output_fns = scancrop.save_images(self.get_real_path(), lines, self.width, self.height, options, self.get_output_path())
        for fn in output_fns:
            File.from_fs(fn, self.folder.output_folder)
        self.done_output = True
        self.save()

    # Add Scan file to database from local filesystem (detects existing if unmoved)
    @staticmethod
    def from_fs(full_name, folder):
        utils.log("Found scan file: %s/%s" % (folder.name, full_name))

        # Get file name/path
        name, extension = os.path.splitext(full_name)
        extension = extension[1:]
        real_path = folder.get_real_path() + full_name

        if extension.lower() not in ["jpg", "jpeg", "png"]:
            return None

        # Search for scan already in database
        scan_qs = Scan.objects.filter(name=name, folder=folder)
        if scan_qs.exists():
            return scan_qs.first()

        # Get image dimensions and orientation
        exif_data = File.get_exif(real_path)
        exif_width = utils.get_if_exist(exif_data, ["EXIF", "ExifImageWidth"])
        exif_height = utils.get_if_exist(exif_data, ["EXIF", "ExifImageLength"])
        if exif_width and exif_height:
            width = exif_width
            height = exif_height
        else:
            image = Image.open(real_path)
            width = image.size[0]
            height = image.size[1]
            image.close()
        orientation = utils.get_if_exist(exif_data, ["Image", "Orientation"])

        utils.log("Adding scan to database: %s/%s" % (folder.name, full_name))

        # Create new scan object
        scan = Scan.objects.create(name=name, format=extension, folder=folder, width=width, height=height, orientation=orientation)
        scan.save()

        return scan
