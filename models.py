from django.conf import settings
from django.contrib.auth.models import User
from django.db import models

import cv2
import datetime
import exifread
import json
import math
import mutagen
import numpy
import os
import piexif
import traceback

from PIL import Image

from .membership.models import *
from . import utils

cascades = {}


# Base class for Folder and RootFolder
class BaseFolder(models.Model):
    class Meta:
        abstract = True

    # Get filenames from filesystem
    def get_fs_filenames(self):
        return os.listdir(self.get_real_path())

    @property
    def file_count(self):
        subfolder_count = sum([folder.file_count for folder in Folder.objects.filter(parent=self.get_folder_instance())])
        file_count = File.objects.filter(folder=self.get_folder_instance()).count()
        return subfolder_count + file_count

    @property
    def length(self):
        subfolder_length = sum([folder.length for folder in Folder.objects.filter(parent=self.get_folder_instance())])
        file_length = sum([file.length for file in File.objects.filter(folder=self.get_folder_instance())])
        return subfolder_length + file_length

    # Scan the local filesystem for new files
    def scan_filesystem(self):
        utils.log("Scanning folder: %s" % self.name)
        real_path = self.get_real_path()
        files = self.get_fs_filenames()
        for filename in files:
            if os.path.isdir(real_path + filename):
                Folder.from_fs(filename, self.get_folder_instance())
            else:
                File.from_fs(filename, self.get_folder_instance())

    # Clear non-existant files/folders from the database
    def prune_database(self):
        utils.log("Pruning database of folder: %s" % self.name)
        folders = Folder.objects.filter(parent=self.get_folder_instance())
        for folder in folders:
            folder.prune_database()

        files = File.objects.filter(folder=self.get_folder_instance())
        for file in files:
            if not os.path.isfile(file.get_real_path()):
                utils.log("Clearing file from database: %s/%s" % (self.name, file.id))
                file.delete()

        if not os.path.isdir(self.get_real_path()):
            if "folder" in self.__dict__:
                self.folder.delete()
            self.delete()

    # Detect faces in files in the folder
    def detect_faces(self):
        utils.log("Detecting faces in folder: %s" % self.name)

        if self.type == "root_folder":
            global cascades
            cascades["face"] = cv2.CascadeClassifier(settings.BASE_DIR + "/fileserver/data/haarcascade_frontalface_alt.xml")
            cascades["eye"] = cv2.CascadeClassifier(settings.BASE_DIR + "/fileserver/data/haarcascade_eye.xml")
            cascades["left_eye"] = cv2.CascadeClassifier(settings.BASE_DIR + "/fileserver/data/haarcascade_lefteye_2splits.xml")
            cascades["right_eye"] = cv2.CascadeClassifier(settings.BASE_DIR + "/fileserver/data/haarcascade_righteye_2splits.xml")

        folders = Folder.objects.filter(parent=self.get_folder_instance())
        for folder in folders:
            folder.detect_faces()

        files = File.objects.filter(folder=self.get_folder_instance())
        for file in files:
            file.detect_faces()


# Folder class
class Folder(BaseFolder):
    name = models.TextField()
    type = "folder"
    parent = models.ForeignKey("Folder", on_delete=models.CASCADE, related_name="+", null=True, blank=True)
    geotag = None

    def __str__(self):
        return self.name

    def get_folder_instance(self):
        return self

    # Return the full path of the folder
    def get_path(self):
        if self.parent is None:
            return self.name.rstrip("/") + "/"
        else:
            return self.parent.get_path() + self.name.strip("/") + "/"

    # Return the disk path of the folder
    def get_real_path(self):
        if self.parent is None:
            return RootFolder.objects.filter(folder=self).first().get_real_path()
        else:
            return self.parent.get_real_path() + self.name.strip("/") + "/"

    def get_children(self, isf):
        children = list(Folder.objects.filter(parent=self))
        if isf:
            all_folders = children
            for child in children:
                all_folders += child.get_children(True)
            return all_folders
        else:
            return children

    def get_files(self, isf=False):
        files = list(File.objects.filter(folder=self))
        if isf:
            all_files = files
            for child in self.get_children(True):
                all_files += child.get_files()
            return all_files
        else:
            return files

    # Fetch a folder from a path
    @staticmethod
    def get_from_path(path):
        folders = Folder.objects.all()

        for folder in folders:
            if folder.get_path() == path:
                return folder

        return None

    # Read a new folder from the filesystem
    @staticmethod
    def from_fs(name, parent):
        folder_qs = Folder.objects.filter(name=name, parent=parent)
        if folder_qs.exists():
            folder = folder_qs.first()
        else:
            folder = Folder.objects.create(name=name, parent=parent)

        folder.scan_filesystem()
        return folder


# Root folder class
class RootFolder(BaseFolder):
    name = models.TextField()
    type = "root_folder"
    real_path = models.TextField()
    folder = models.OneToOneField("Folder", on_delete=models.CASCADE, related_name="+", null=True, blank=True)

    @classmethod
    def post_create(cls, sender, instance, created, *args, **kwargs):
        if created:
            instance.folder = Folder.objects.create(name=instance.name)
            instance.save()

    def __str__(self):
        return self.name

    def get_folder_instance(self):
        return self.folder

    # Return the disk path
    def get_real_path(self):
        return self.real_path.rstrip("/") + "/"

    # Fully update the database for this folder
    def update_database(self):
        try:
            self.scan_filesystem()
            self.prune_database()
            self.detect_faces()
            Face.recognize_faces()
        except Exception as e:
            utils.log(traceback.format_exc())

models.signals.post_save.connect(RootFolder.post_create, sender=RootFolder)


# Album class
class Album(models.Model):
    name = models.TextField()
    files = models.ManyToManyField("File", through="AlbumFile")
    parent = models.ForeignKey("Album", on_delete=models.CASCADE, related_name="+", null=True, blank=True)
    # created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    date_created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.get_path()

    # TODO redefine some of these as @property methods

    def get_path(self):
        if self.parent is None:
            return self.name + "/"
        else:
            return self.parent.get_path() + self.name + "/"

    def get_children(self):
        return Album.objects.filter(parent=self)

    # Recursively get all child albums
    def get_all_children(self):
        all_children = []
        for child in self.get_children():
            all_children.append(child)
            all_children += child.get_all_children()
        return all_children

    # Get all files in album and its children
    def get_files(self):
        all_files = self.files.all()
        for child in self.get_all_children():
            all_files |= child.files.all()
        return all_files

    # Get all album-file relationships
    def get_file_rels(self):
        album_files = AlbumFile.objects.filter(album=self)
        for child in self.get_all_children():
            album_files |= AlbumFile.objects.filter(album=child)
        return album_files

    # Get the number of files in the album
    def get_file_count(self):
        return len(self.get_files())

    # Remove a file from parents of the album (before adding it to the album)
    def remove_from_parents(self, to_remove):
        if self.parent is not None:
            album_file_qs = AlbumFile.objects.filter(album=self.parent, file=to_remove)
            album_file_qs.delete()
            self.parent.remove_from_parents(to_remove)

    # Fetch an album from a path
    @staticmethod
    def get_from_path(path):
        albums = Album.objects.all()
        path = path.rstrip("/") + "/"

        for album in albums:
            if album.get_path() == path:
                return album

        return None


# Album/file pairing
class AlbumFile(models.Model):
    album = models.ForeignKey(Album, on_delete=models.CASCADE, related_name="+")
    file = models.ForeignKey("File", on_delete=models.CASCADE, related_name="+")
    # added_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    date_added = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.album) + " - " + str(self.file)


# File class
class File(models.Model):
    id = models.CharField(max_length=24, primary_key=True)
    name = models.TextField(null=True)
    folder = models.ForeignKey("Folder", on_delete=models.CASCADE, related_name="+")
    type = models.TextField(default="file")
    format = models.TextField(null=True)
    length = models.PositiveIntegerField()
    is_starred = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    timestamp = models.DateTimeField(null=True)
    scanned_faces = models.BooleanField(default=False)

    width = models.PositiveIntegerField(null=True)
    height = models.PositiveIntegerField(null=True)
    orientation = models.PositiveIntegerField(null=True)
    duration = models.DurationField(null=True)
    geotag = models.OneToOneField("GeoTag", on_delete=models.SET_NULL, null=True, blank=True)
    metadata = models.TextField(default="{}")
    # TODO get video details using ffmpeg https://gist.github.com/oldo/dc7ee7f28851922cca09

    def __str__(self):
        return "%s (%s.%s)" % (self.name, self.id, self.format)

    # Return the (non-disk) path of the file
    def get_path(self):
        return self.folder.get_path() + self.id + "." + self.format

    # Return the disk path of the file
    def get_real_path(self):
        return self.folder.get_real_path() + self.id + "." + self.format

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

    @property
    def faces(self):
        return list(Face.objects.filter(file=self))

    # Read a new file from the filesystem
    @staticmethod
    def from_fs(full_name, folder):
        utils.log("Found file: %s/%s" % (folder.name, full_name))

        # Get file name/path
        name, extension = os.path.splitext(full_name)
        real_path = folder.get_real_path() + full_name

        # Search for file already in database
        file_qs = File.objects.filter(id=name)
        if file_qs.exists():
            file = file_qs.first()
            if file.folder != folder:
                file.folder = folder
                file.save()
            return file

        utils.log("Adding file to database: %s/%s" % (folder.name, full_name))

        # Create new file dictionary
        new_file = {
            "folder": folder,
            "type": File.get_type(extension),
            "format": extension[1:]
        }

        # Get EXIF and mutagen data from file
        exif_data = File.get_exif(real_path)
        mutagen_data = mutagen.File(real_path, easy=True) or {}

        # Get file title from exif or name
        exif_title = utils._get_if_exist(exif_data, ["Image", "ImageDescription"])
        mutagen_title = utils._get_if_exist(mutagen_data, ["title"]) or utils._get_if_exist(mutagen_data, ["©nam"])
        if exif_title:
            new_file["name"] = exif_data["Image"]["ImageDescription"]
            write_title = False
        elif mutagen_title:
            new_file["name"] = mutagen_title
            write_title = False
        else:
            new_file["name"] = name
            write_title = True

        # Get file size
        new_file["length"] = os.path.getsize(real_path)

        # Get file timestamp
        exif_timestamp = utils._get_if_exist(exif_data, ["EXIF", "DateTimeOriginal"]) or utils._get_if_exist(exif_data, ["Image", "DateTime"])
        if exif_timestamp:
            new_file["timestamp"] = datetime.datetime.strptime(exif_timestamp, "%Y:%m:%d %H:%M:%S")
        else:
            new_file["timestamp"] = datetime.datetime.fromtimestamp(os.path.getmtime(real_path))

        # Get image dimensions
        exif_width = utils._get_if_exist(exif_data, ["EXIF", "ExifImageWidth"])
        exif_height = utils._get_if_exist(exif_data, ["EXIF", "ExifImageLength"])
        if exif_width and exif_height:
            new_file["width"] = exif_width
            new_file["height"] = exif_height
        elif new_file["type"] == "image":
            image = Image.open(real_path)
            new_file["width"] = image.size[0]
            new_file["height"] = image.size[1]
            image.close()

        # Extract EXIF orientation
        new_file["orientation"] = utils._get_if_exist(exif_data, ["Image", "Orientation"])

        exif_geotag = GeoTag.from_exif(exif_data)
        if exif_geotag:
            new_file["geotag"] = exif_geotag
        # TODO get from other metadata if possible

        # Assign metadata dictionary to new file
        if exif_data:
            new_file["metadata"] = json.dumps(exif_data, default=lambda obj: str(obj) if isinstance(obj, bytes) else obj.__dict__)
        elif mutagen_data:
            new_file["metadata"] = json.dumps(mutagen_data, default=lambda obj: str(obj) if isinstance(obj, bytes) else obj.__dict__)

        # Generate ID for file
        new_file["id"] = File.get_id_name(new_file)

        # Create new file object
        file = File.objects.create(**new_file)

        # Get full path of new filename
        new_real_path = folder.get_real_path() + new_file["id"] + extension

        # Rename file
        os.rename(real_path, new_real_path)

        # Write file title to EXIF
        if write_title:
            try:
                exif_dict = piexif.load(new_real_path)
                exif_dict["0th"][piexif.ImageIFD.ImageDescription] = new_file["name"]
                piexif.insert(piexif.dump(exif_dict), new_real_path)
            except:
                mutagen_file = mutagen.File(new_real_path, easy=True)
                if mutagen_file is not None:
                    mutagen_file["title"] = new_file["name"]
                    mutagen_file.save()

        return file

    types = {
        "image": ["jpg", "jpeg", "png"],
        "video": ["mp4", "mov"]
    }

    # Get the file type from extension
    @staticmethod
    def get_type(extension):
        if not extension:
            return "file"

        extension = extension[1:].lower()
        for file_type in File.types:
            if extension in File.types[file_type]:
                return file_type

        return "file"

    # Extract exif dict from file path
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

    # Generate the file ID
    @staticmethod
    def get_id_name(file):
        dt_id = file["timestamp"].strftime("%Y-%m-%d_%H-%M-%S")

        file_qs = File.objects.filter(id__startswith=dt_id)
        if file_qs.exists():
            max_id = int(file_qs.last().id[20:], 16)
        else:
            max_id = 0

        return dt_id + "_" + "%04x" % (max_id + 1)

    # Detect faces in a file
    def detect_faces(self):
        if self.type != "image" or self.scanned_faces:
            return

        global cascades

        config = {
            "max_size": 1000
        }

        utils.log("Detecting faces in file: %s" % str(self))

        full_image = cv2.imread(self.get_real_path())
        height, width = full_image.shape[:2]
        ratio = config["max_size"] / max(width, height)
        if ratio > 1:
            ratio = 1
        scaled_image = cv2.resize(full_image, (round(width * ratio), round(height * ratio)))
        grayscale = cv2.cvtColor(scaled_image, cv2.COLOR_BGR2GRAY)
        full_grayscale = cv2.cvtColor(full_image, cv2.COLOR_BGR2GRAY)

        faces = cascades["face"].detectMultiScale(grayscale, 1.1, 5, 0, (round(config["max_size"] / 50), round(config["max_size"] / 50)))

        for x, y, w, h in faces:
            face_mat = full_grayscale[int(round(y / ratio)): int(round((y + h) / ratio)), int(round(x / ratio)): int(round((x + w) / ratio))]
            eyes = Face.get_eyes(face_mat)
            if eyes is None:
                eyes_found = False
                rotation = 0
                eyes = ((0, -h / (8 * 1.625)), (0, -h / (8 * 1.625)))
            else:
                eyes_found = True
                rotation = Face.get_rotation(eyes)

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

            Face.objects.create(**face_dict)

        self.scanned_faces = True
        self.save()

        utils.log("Detected %s faces in file: %s" % (len(faces), str(self)))


# Group for people
class PersonGroup(models.Model):
    name = models.TextField()

    def __str__(self):
        return self.name


# Person class
class Person(models.Model):
    full_name = models.TextField()
    group = models.ForeignKey(PersonGroup, on_delete=models.SET_DEFAULT, default=0, related_name="+")
    # created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    date_created = models.DateTimeField(auto_now_add=True)

    @property
    def thumbnail(self):
        faces = [face for face in self.get_faces() if face.status <= 1]
        if self.id != 0 and len(faces) > 0:
            return max(faces, key=lambda face: face.rect_w)
        else:
            return None

    def __str__(self):
        return "%s (%s)" % (self.full_name, str(self.group))

    def get_faces(self):
        return Face.objects.filter(person=self, status__lt=4)


# Face class
class Face(models.Model):
    rect_x = models.PositiveIntegerField()
    rect_y = models.PositiveIntegerField()
    rect_w = models.PositiveIntegerField()
    rect_h = models.PositiveIntegerField()
    eyes_found = models.BooleanField()
    rect_r = models.FloatField()
    eye_l_x = models.PositiveIntegerField()
    eye_l_y = models.PositiveIntegerField()
    eye_r_x = models.PositiveIntegerField()
    eye_r_y = models.PositiveIntegerField()
    file = models.ForeignKey(File, on_delete=models.CASCADE, related_name="+")
    person = models.ForeignKey(Person, on_delete=models.SET_DEFAULT, default=0, related_name="+")
    uncertainty = models.FloatField()

    STATUS_OPTIONS = (
        (0, "Confirmed (root)"),
        (1, "Confirmed (user)"),
        (2, "Predicted"),
        (3, "Unassigned"),
        (4, "Ignored"),
        (5, "Removed")
    )
    status = models.PositiveIntegerField(choices=STATUS_OPTIONS)

    # Fetch the actual face (pixels) from the image file
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

        if "quality" in kwargs:
            quality = kwargs["quality"]
        else:
            quality = 75

        full_image = cv2.cvtColor(cv2.imread(self.file.get_real_path()), color)

        # Define custom rounding function
        def cround(n):
            return math.ceil(n) if n % 1 >= 0.5 else math.floor(n)

        # Crop image down to bounding box
        diagonal = math.sqrt(w ** 2 + h ** 2)
        diag_angle = math.atan(h / w)
        bbox_w = max(diagonal * abs(math.cos(diag_angle - abs(math.radians(r)))), w)
        bbox_h = max(diagonal * abs(math.sin(-diag_angle - abs(math.radians(r)))), h)  # TODO not sure if this is a permanent solution or not, will have to see
        bbox_w_rounded = cround(x + bbox_w / 2) - cround(x - bbox_w / 2)
        bbox_h_rounded = cround(y + bbox_h / 2) - cround(y - bbox_h / 2)
        bbox_image = numpy.zeros(shape=(bbox_h_rounded, bbox_w_rounded, 3), dtype=numpy.uint8)
        bbox_image[cround(-min(y - bbox_h / 2, 0)): bbox_h_rounded, cround(-min(x - bbox_w / 2, 0)): bbox_w_rounded] = full_image[cround(max(y - bbox_h / 2, 0)): cround(y + bbox_h / 2), cround(max(x - bbox_w / 2, 0)): cround(x + bbox_w / 2)]

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
        else:
            scaled_image = bbox_image

        # Rotate image
        M = cv2.getRotationMatrix2D((x, y), r, 1)
        rot_image = cv2.warpAffine(scaled_image, M, (cround(bbox_w), cround(bbox_h)))

        # Crop down to face
        face_image = rot_image[cround(y - h / 2): cround(y + h / 2), cround(x - w / 2): cround(x + w / 2)]

        return face_image

    @staticmethod
    def get_eyes(face):
        global cascades

        height, width = face.shape[:2]

        # Detect all possible eyes
        both_eyes = [(e[0] + e[2] / 2, e[1] + e[3] / 2) for e in cascades["eye"].detectMultiScale(face, 1.1, 5, 0, (round(width / 6), round(height / 6)), (round(width / 4), round(height / 4)))]
        left_eyes = [(e[0] + e[2] / 2, e[1] + e[3] / 2) for e in cascades["left_eye"].detectMultiScale(face, 1.1, 5, 0, (round(width / 7), round(height / 7)), (round(width / 3), round(height / 3)))]
        right_eyes = [(e[0] + e[2] / 2, e[1] + e[3] / 2) for e in cascades["right_eye"].detectMultiScale(face, 1.1, 5, 0, (round(width / 7), round(height / 7)), (round(width / 3), round(height / 3)))]

        both_eyes.sort(key=lambda eye: eye[1])
        left_eyes.sort(key=lambda eye: eye[1])
        right_eyes.sort(key=lambda eye: eye[1])

        # Choose best eyes
        eyes = Face.choose_eyes(left_eyes, right_eyes, both_eyes, width, height)

        return eyes

    @staticmethod
    def choose_eyes(left_eyes, right_eyes, both_eyes, width, height):
        left_eye = Face.choose_eye(left_eyes + both_eyes + right_eyes, False, width, height)
        right_eye = Face.choose_eye(right_eyes + both_eyes + left_eyes, True, width, height)

        if left_eye is None or right_eye is None:
            return None
        else:
            return [left_eye, right_eye]

    @staticmethod
    def choose_eye(all_eyes, side, width, height):
        for eye in all_eyes:
            eye_side = Face.get_eye_side(eye, width, height)
            if eye_side == side:
                return eye

        return None

    @staticmethod
    def get_eye_side(eye, width, height):
        x = eye[0] - width / 2
        y = height / 2 - eye[1]

        return y / x < 0

    @staticmethod
    def get_rotation(eyes):
        x_diff = eyes[0][0] - eyes[1][0]
        y_diff = eyes[0][1] - eyes[1][1]

        return math.degrees(math.atan(y_diff / x_diff))

    # Recognise faces (not folder-limited)
    @staticmethod
    def recognize_faces():
        utils.log("Recognising faces found previously")

        face_recognizer = cv2.face.LBPHFaceRecognizer_create(2, 16, 16, 16)
        untrained = True

        known_faces = Face.objects.filter(person__id__gt=0, status__lt=3)
        print("Known faces:", len(known_faces))
        if len(known_faces) == 0:
            utils.log("No known faces found, not running recognition")
            return

        utils.log("Training face recognition model")

        for i in range(0, known_faces.count(), 50):
            images, labels = [], []
            for face in known_faces[i: i + 50]:
                images.append(face.get_image(cv2.COLOR_BGR2GRAY))
                labels.append(face.person.id)

            if untrained:
                face_recognizer.train(images, numpy.array(labels))
                untrained = False
            else:
                face_recognizer.update(images, numpy.array(labels))

        utils.log("Trained face recognition model")

        unknown_faces = Face.objects.filter(status__lt=4, status__gt=1)
        print("Unknown faces:", len(unknown_faces))

        utils.log("Predicting face identities")

        for face in unknown_faces:
            label, confidence = face_recognizer.predict(face.get_image(cv2.COLOR_BGR2GRAY))
            print("Predicted %s with confidence %s" % (Person.objects.filter(id=label).first().full_name, confidence))
            if label == -1:
                label = 0
            else:
                face.status = 2
            face.person = Person.objects.filter(id=label).first()
            face.uncertainty = confidence
            face.save()

        utils.log("Predicted face identities")

        # TODO test


# Area grouping for geotags
class GeoTagArea(models.Model):
    name = models.TextField()
    address = models.TextField()
    latitude = models.FloatField()
    longitude = models.FloatField()
    radius = models.FloatField()
    # created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    date_created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


# Geotag for a file
class GeoTag(models.Model):
    latitude = models.FloatField(null=True)
    longitude = models.FloatField(null=True)
    area = models.ForeignKey(GeoTagArea, on_delete=models.CASCADE, related_name="+", null=True)
    # created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+", null=True)
    date_created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return "%s, %s (%s)" % (round(self.latitude, 2), round(self.longitude, 2), self.area)

    # Convert EXIF GPS co-ordinates to float in degrees
    @staticmethod
    def exif_to_degrees(values):
        d = float(values[0].num) / float(values[0].den)
        m = float(values[1].num) / float(values[1].den)
        s = float(values[2].num) / float(values[2].den)

        return d + (m / 60.0) + (s / 3600.0)

    # Create geotag object from exif data
    @staticmethod
    def from_exif(exif_data):
        exif_latitude = utils._get_if_exist(exif_data, ["GPS", "GPSLatitude"])
        exif_latitude_ref = utils._get_if_exist(exif_data, ["GPS", "GPSLatitudeRef"])
        exif_longitude = utils._get_if_exist(exif_data, ["GPS", "GPSLongitude"])
        exif_longitude_ref = utils._get_if_exist(exif_data, ["GPS", "GPSLongitudeRef"])

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
