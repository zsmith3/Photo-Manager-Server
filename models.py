# Standard imports
import datetime
import functools
import json
import math
import os
import traceback

# Django imports
from django.db import models

# Third-party imports
import cv2
import exifread
import mutagen
import numpy
import piexif
from PIL import Image

# Local imports
from . import utils
from .membership.models import *


# Global Haar cascades dict
cascades = {}


class BaseFolder(models.Model):
    """ Abstract base class for Folder and RootFolder """

    class Meta:
        abstract = True

    @property
    def file_count(self):
        """ Number of files in folder

        Includes all files in subfolders.

        Returns
        -------
        int
            Total file count
        """

        subfolder_count = sum([folder.file_count for folder in Folder.objects.filter(parent=self.get_folder_instance())])
        file_count = File.objects.filter(folder=self.get_folder_instance()).count()
        return subfolder_count + file_count

    @property
    def length(self):
        """ Size of folder

        Given in bytes, includes all files in top-level folder and subfolders.

        Returns
        -------
        int
            Total size (bytes)
        """

        subfolder_length = sum(folder.length for folder in Folder.objects.filter(parent=self.get_folder_instance()))
        file_length = File.objects.filter(folder=self.get_folder_instance()).aggregate(models.Sum("length"))["length__sum"] or 0
        return subfolder_length + file_length

    def get_fs_filenames(self):
        """ Get filenames in folder from local filesystem

        Returns
        -------
        list of str
            List of filenames (not full paths)
        """

        return os.listdir(self.get_real_path())

    def scan_filesystem(self):
        """ Scan the local filesystem for new files

        Recursively scans the full tree at the real location of this folder,
        adding any files to the database which are not already present.
        Also detects movement of existing files, provided they are still within the Root Folder.
        """

        utils.log("Scanning folder: %s" % self.name)
        real_path = self.get_real_path()
        files = self.get_fs_filenames()
        for filename in files:
            if os.path.isdir(real_path + filename):
                Folder.from_fs(filename, self.get_folder_instance())
            else:
                File.from_fs(filename, self.get_folder_instance())

    def prune_database(self):
        """ Clear deleted files/folders from the database

        Recursively finds and removes from the database any files/folders in this folder which are not found in their expected filesystem location.
        This should only be run after running scan_filesystem, as it will not detect file movements.
        """

        utils.log("Pruning database of folder: %s" % self.name)

        # Prune subfolders
        folders = Folder.objects.filter(parent=self.get_folder_instance())
        for folder in folders:
            folder.prune_database()

        # Prune top-level files
        files = File.objects.filter(folder=self.get_folder_instance())
        for file in files:
            if not os.path.isfile(file.get_real_path()):
                utils.log("Clearing file from database: %s/%s" % (self.name, file.file_id))
                file.delete()

        # Delete self if needed
        if not os.path.isdir(self.get_real_path()):
            if "folder" in self.__dict__:
                self.folder.delete()
            self.delete()

    def detect_faces(self):
        """ Detect faces in image files in the folder (and subfolders)

        Recursively scans all files in subfolders which have not already been marked as scanned. Uses Haar cascades provided by OpenCV.
        """

        utils.log("Detecting faces in folder: %s" % self.name)

        # Load cascades if needed
        if isinstance(self, RootFolder):
            global cascades
            cascades["face"] = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_alt.xml")
            cascades["eye"] = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")
            cascades["left_eye"] = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_lefteye_2splits.xml")
            cascades["right_eye"] = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_righteye_2splits.xml")

        # Detect faces in subfolders
        folders = Folder.objects.filter(parent=self.get_folder_instance())
        for folder in folders:
            folder.detect_faces()

        # Detect faces in top-level files
        files = File.objects.filter(folder=self.get_folder_instance())
        for file in files:
            file.detect_faces()


class Folder(BaseFolder):
    """ Folder model

    Attributes
    ----------
    name : TextField
        Name of the folder
    parent : ForeignKey(Folder)
        Parent folder
    """

    name = models.TextField()
    parent = models.ForeignKey("Folder", on_delete=models.CASCADE, related_name="+", null=True, blank=True)

    @staticmethod
    def get_from_path(path):
        """ Find a folder from its path

        Parameters
        -------
        path : str
            The exact virtual path to the folder.

        Returns
        -------
        Folder or None
            The Folder instance found, or None if not found
        """

        folders = Folder.objects.all()

        for folder in folders:
            if folder.get_path() == path:
                return folder

        return None

    @staticmethod
    def from_fs(name, parent):
        """ Load a folder into the database from the filesystem

        Recursively loads all files, including subfolder contents.

        Parameters
        -------
        name : str
            The name of the new folder.
        parent : Folder
            The (already created) parent Folder instance.

        Returns
        -------
        Folder
            The newly created Folder instance
        """

        # Create folder if needed
        folder_qs = Folder.objects.filter(name=name, parent=parent)
        if folder_qs.exists():
            folder = folder_qs.first()
        else:
            folder = Folder.objects.create(name=name, parent=parent)

        # Recursively load folder contents
        folder.scan_filesystem()

        return folder

    def __str__(self):
        return self.name

    def get_folder_instance(self):
        """ Return self for standard folders

        This method exists to make Folder interchangeable with RootFolder.

        Returns
        -------
        Folder
            self
        """
        return self

    def get_path(self):
        """ Get the full (virtual) path to the folder

        Includes both the Root Folder name and name of this folder.
        Does not include the real filesystem location.

        Returns
        -------
        str
            Virtual path to folder
        """

        if self.parent is None:
            return self.name.rstrip("/") + "/"
        else:
            return self.parent.get_path() + self.name.strip("/") + "/"

    def get_real_path(self):
        """ Get the full (real) path to the folder in the local filesystem

        Returns
        -------
        str
            Real path to folder
        """

        if self.parent is None:
            return RootFolder.objects.filter(folder=self).first().get_real_path()
        else:
            return self.parent.get_real_path() + self.name.strip("/") + "/"

    def get_children(self, include_subfolders):
        """ Get subfolders in folder

        Parameters
        -------
        include_subfolders : bool
            If False, only top-level subfolders will be included. If True, they will be scanned recursively for all descendants.

        Returns
        -------
        QuerySet of Folder
            Set of child Folder instances
        """

        children = Folder.objects.filter(parent=self)
        if include_subfolders:
            return functools.reduce((lambda x, y: x | y), (child.get_children(True) for child in children), children)
        else:
            return children

    def get_files(self, include_subfolders=False):
        """ Get Files in folder

        Parameters
        -------
        include_subfolders : bool
            If False, only top-level files will be included.
            If True, subfolders will be scanned recursively for all files.
            Defaults to False.

        Returns
        -------
        QuerySet of File
            Set of Files in folder
        """

        files = File.objects.filter(folder=self)
        if include_subfolders:
            return functools.reduce((lambda x, y: x | y), (child.get_files() for child in self.get_children(True)), files)
        else:
            return files


class RootFolder(BaseFolder):
    """ Root Folder model

    Attributes
    ----------
    name : TextField
        Name of the root folder
    real_path : TextField
        Real path to folder in local filesystem
    folder : OneToOneField(Folder)
        Reference to the standard Folder model instance attached to this
    """

    name = models.TextField()
    real_path = models.TextField()
    folder = models.OneToOneField("Folder", on_delete=models.CASCADE, related_name="+", null=True, blank=True)

    @classmethod
    def post_create(cls, sender, instance, created, *args, **kwargs):
        """ Create attached Folder model """

        if created:
            instance.folder = Folder.objects.create(name=instance.name)
            instance.save()

    def __str__(self):
        return self.name

    def get_folder_instance(self):
        """ Return attached Folder instance

        This method exists to make Folder interchangeable with RootFolder.

        Returns
        -------
        Folder
            self.folder
        """

        return self.folder

    def get_real_path(self):
        """ Get the full (real) path to the root folder in the local filesystem

        Returns
        -------
        str
            Real path to root folder
        """

        return self.real_path.rstrip("/") + "/"

    def update_database(self):
        """ Run all database updates for this Root Folder

        Scans the filesystem for new or moved files,
        removes deleted files from the database,
        detects any faces in unscanned image files
        and attempts to recognize faces found.
        """

        try:
            self.scan_filesystem()
            self.prune_database()
            self.detect_faces()
            Face.recognize_faces()
        except Exception:
            utils.log(traceback.format_exc())


# Attach method to run when RootFolder instances are created
models.signals.post_save.connect(RootFolder.post_create, sender=RootFolder)


# Album class
class Album(models.Model):
    """ Album model

    Attributes
    ----------
    name : TextField
        Name of the album
    parent : ForeignKey(Album)
        The parent album (None for root albums)
    files : ManyToManyField(File)
        A list of top-level files found in this album (not including those in child albums)
    date_created : DateTimeField
        The date upon which the album was first created
    """
    # TODO look into proper database history type stuff

    name = models.TextField()
    parent = models.ForeignKey("Album", on_delete=models.CASCADE, related_name="+", null=True, blank=True)
    files = models.ManyToManyField("File", through="AlbumFile")
    # created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    date_created = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def get_from_path(path):
        """ Find an album from its path

        Returns
        -------
        Album or None
            The Album instance found, or None if not found
        """

        albums = Album.objects.all()
        path = path.rstrip("/") + "/"

        for album in albums:
            if album.get_path() == path:
                return album

        return None

    def __str__(self):
        return self.get_path()

    @property
    def path(self):
        """ Full path to album

        Returns
        -------
        str
            Path to album
        """

        if self.parent is None:
            return self.name + "/"
        else:
            return self.parent.get_path() + self.name + "/"

    @property
    def file_count(self):
        """ Number of files in the album (including its children)

        Returns
        -------
        int
            Number of files found
        """

        return self.get_files().count()

    def get_children(self, recurse=False):
        """ Get child albums

        Parameters
        ----------
        recurse : bool
            If True, will recursively get all child albums.
            If False, will only get top-level children.
            Defaults to False.

        Returns
        -------
        QuerySet of Album
            Child albums
        """

        children = Album.objects.filter(parent=self)
        if recurse:
            return functools.reduce((lambda x, y: x | y), (child.get_children(True) for child in children), children)
        else:
            return children

    def get_files(self):
        """ Get all files in album (including its children)

        Returns
        -------
        QuerySet of File
            Full set of files
        """

        all_files = self.files.all()
        return functools.reduce((lambda x, y: x | y), (child.files.all() for child in self.get_children(True)), all_files)

    def get_file_rels(self):
        """ Get all AlbumFile relationships associated with album and its children

        Returns
        -------
        QuerySet of AlbumFile
            Full set of AlbumFile relationships
        """

        album_files = AlbumFile.objects.filter(album=self)
        return functools.reduce((lambda x, y: x | y), (AlbumFile.objects.filter(album=child) for child in self.get_children(True)), album_files)

    def remove_from_parents(self, to_remove):
        """ Remove a file from parents of the album

        This method is run before adding files to the album, to avoid duplication.

        Parameters
        -------
        to_remove : File
            The file to be removed
        """

        if self.parent is not None:
            album_file_qs = AlbumFile.objects.filter(album=self.parent, file=to_remove)
            album_file_qs.delete()
            self.parent.remove_from_parents(to_remove)


class AlbumFile(models.Model):
    """ Album-File relationship model

    Attributes
    ----------
    album : ForeignKey(Album)
        The Album instance to which the File belongs
    file : ForeignKey(File)
        The File instance which belongs to the Album
    date_added : DateTimeField
        The date upon which the file was added to the album
    """

    album = models.ForeignKey(Album, on_delete=models.CASCADE, related_name="+")
    file = models.ForeignKey("File", on_delete=models.CASCADE, related_name="+")
    # added_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    date_added = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.album) + " - " + str(self.file)


class File(models.Model):
    """ File model

    Attributes
    ----------
    file_id : CharField
        The unique ID used as a local filename, based on the date taken/modified
    name : TextField
        The name (title) of the file (not the actual local filename)
    folder : ForeignKey(Folder)
        The Folder instance to which the file belongs
    type : TextField({'file', 'image', 'video'})
        The file type (as a broad category)
    format : TextField
        The file extension
    length : PositiveIntegerField
        The size (in bytes) of the file
    is_starred : bool
        Whether or not the file has been starred by a user
    is_deleted : bool
        Whether or not the file has been marked for deletion by a user
    timestamp : DateTimeField
        The date taken (if available) or date modified of the file
    scanned_faces : BooleanField
        Whether or not the file (if an image) has been scanned for faces

    width : PositiveIntegerField
        The width of the (image or video) file in pixels
    height : PositiveIntegerField
        The height of the (image or video) file in pixels
    orientation : PositiveIntegerField
        The EXIF orientation of the (image) file
    duration : DurationField
        The duration of the (video) file
    geotag : OneToOneField(GeoTag)
        The GeoTag instance for the (image or video) file
    metadata : TextField
        The file metadata (e.g. EXIF), stored as a JSON object
    """

    FILE_TYPES = (
        ("image", "Image file"),
        ("video", "Video file"),
        ("file", "Non-image file")
    )

    file_id = models.CharField(max_length=24)
    name = models.TextField(null=True)
    folder = models.ForeignKey("Folder", on_delete=models.CASCADE, related_name="+")
    type = models.TextField(choices=FILE_TYPES, default="file")
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

    # File format-type dict
    types = {
        "image": ["jpg", "jpeg", "png"],
        "video": ["mp4", "mov"]
    }

    @staticmethod
    def from_fs(full_name, folder):
        """ Read a file from the filesystem, and add to database if not yet present

        This method should detect new files and file movements, and ignore unchanged files.
        It does not (currently) detect other changes to files.

        Parameters
        ----------
        full_name : str
            The full name (including extension) of the file
        folder : Folder
            The Folder instance in which the file is found

        Returns
        -------
        File
            The (created or existing) File instance
        """

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
        for exif_timestamp in [utils._get_if_exist(exif_data, ["EXIF", "DateTimeOriginal"]), utils._get_if_exist(exif_data, ["Image", "DateTime"]), utils._get_if_exist(exif_data, ["EXIF", "DateTimeDigitized"])]:
            try:
                new_file["timestamp"] = datetime.datetime.strptime(exif_timestamp, "%Y:%m:%d %H:%M:%S")
                break
            except (ValueError, TypeError):
                pass
        if new_file["timestamp"] is None:
            id_timestamp = File.get_id_date(name)
            if id_timestamp is not None:
                new_file["timestamp"] = id_timestamp
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

    # Get the file type from extension
    @staticmethod
    def get_type(extension):
        """ Determine the type of a file from its extension

        Parameters
        ----------
        extension : str
            The filename extension (including preceding dot)

        Returns
        -------
        {'file', 'image', 'video'}
            The file type
        """

        if not extension:
            return "file"

        extension = extension[1:].lower()
        for file_type in File.types:
            if extension in File.types[file_type]:
                return file_type

        return "file"

    @staticmethod
    def get_exif(real_path):
        """ Read exif data from the file at the given path

        Parameters
        ----------
        real_path : str
            The real local filesystem location of the file

        Returns
        -------
        dict
            All EXIF data for file
        """

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
        """ Generate unique file_id from timestamp

        Parameters
        ----------
        file : dict
            Dictionary of File data, including timestamp

        Returns
        -------
        str
            The generated ID
        """

        dt_id = file["timestamp"].strftime("%Y-%m-%d_%H-%M-%S")

        file_qs = File.objects.filter(file_id__startswith=dt_id)
        if file_qs.exists():
            max_id = int(file_qs.last().file_id[20:], 16)
        else:
            max_id = 0

        return dt_id + "_" + "%04x" % (max_id + 1)

    def __str__(self):
        return "%s (%s.%s)" % (self.name, self.file_id, self.format)

    @property
    def albums(self):
        """ All albums to which this file belongs

        Includes all parent albums.

        Returns
        -------
        list of Album
            Full list of albums
        """

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
        """ Faces found in this file

        Returns
        -------
        QuerySet of Face
            Set of Face instances found
        """

        return Face.objects.filter(file=self)

    def get_path(self):
        """ Get full (virtual) path to file

        Includes the file name. Does not include the real filesystem location.

        Returns
        -------
        str
            Path to file
        """

        return self.folder.get_path() + self.file_id + "." + self.format

    def get_real_path(self):
        """ Get the full (real) path to the file in the local filesystem

        Returns
        -------
        str
            Real path to file
        """

        return self.folder.get_real_path() + self.file_id + "." + self.format

    def get_id_date(file_id):
        """ Get the timestamp of a file from its file_id

        Parameters
        ----------
        file_id : str
            The unique ID of the file (from its filename)

        Returns
        -------
        datetime or None
            The timestamp of the file, or None if file_id is malformatted
        """

        try:
            return datetime.datetime.strptime(file_id[: -5], "%Y-%m-%d_%H-%M-%S")
        except ValueError:
            return None

    def detect_faces(self):
        """ Detect faces in (image) file

        Uses OpenCV Haar Cascades.
        Also attempts to find eye locations for any faces found.
        """

        # Return if file is not an image, or if it has already been scanned
        if self.type != "image" or self.scanned_faces:
            return

        # Use globally stored Haar cascades
        global cascades

        # Local config
        config = {
            "max_size": 1000
        }

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
            face_mat = full_grayscale[int(round(y / ratio)): int(round((y + h) / ratio)), int(round(x / ratio)): int(round((x + w) / ratio))]

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

            Face.objects.create(**face_dict)

        # Register that file has now been scanned
        self.scanned_faces = True
        self.save()

        utils.log("Detected %s faces in file: %s" % (len(faces), str(self)))


class PersonGroup(models.Model):
    """ Group of Person model

    Attributes
    ----------
    name : TextField
        The name of the group

    """

    name = models.TextField()

    def __str__(self):
        return self.name


class Person(models.Model):
    """ Person model

    Attributes
    ----------
    full_name : TextField
        The full name of the person
    group : ForeignKey(PersonGroup)
        The group to which the person belongs (default = 0 - Ungrouped)
    date_created : DateTimeField
        The date upon which the person was created
    """

    full_name = models.TextField()
    group = models.ForeignKey(PersonGroup, on_delete=models.SET_DEFAULT, default=0, related_name="+")
    # created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    date_created = models.DateTimeField(auto_now_add=True)

    @property
    def thumbnail(self):
        """ A face selected as the thumbnail for this person

        Selects the largest confirmed face.

        Returns
        -------
        Face or None
            The chosen Face, or None if none available
        """

        face_set = Face.objects.filter(person=self, status__lt=2).order_by("-rect_w")

        if self.id != 0 and face_set.exists():
            return face_set.first()
        else:
            return None

    def __str__(self):
        return "%s (%s)" % (self.full_name, str(self.group))

    def get_faces(self):
        """ Get faces identified as belonging to person

        Includes both confirmed and unconfirmed identifications.

        Returns
        -------
        QuerySet of Face
            The set of Faces found
        """
        return Face.objects.filter(person=self, status__lt=4)


class Face(models.Model):
    """ Face model

    Attributes
    ----------
    rect_x : PositiveIntegerField
        X co-ordinate of the centre of the face rectangle
    rect_y : PositiveIntegerField
        Y co-ordinate of the centre of the face rectangle
    rect_w : PositiveIntegerField
        Width of the face rectangle
    rect_h : PositiveIntegerField
        Height of the face rectangle
    rect_r : FloatField
        Angle (degrees) of rotation of the face rectangle

    eyes_found : BooleanField
        Whether or not eyes where successfully identified on the face
    eye_l_x : PositiveIntegerField
        X co-ordinate of centre of left eye
    eye_l_y : PositiveIntegerField
        Y co-ordinate of centre of left eye
    eye_r_x : PositiveIntegerField
        X co-ordinate of centre of right eye
    eye_r_y : PositiveIntegerField
        Y co-ordinate of centre of right eye

    file : ForeignKey(File)
        Image file in which the face is found
    person : ForeignKey(Person)
        Person to which the face belongs
    uncertainty : FloatField
        Degree of uncertainty in automatic recognition
    status : PositiveIntegerField
        Status of face identification
    """

    STATUS_OPTIONS = (
        (0, "Confirmed (root)"),
        (1, "Confirmed (user)"),
        (2, "Predicted"),
        (3, "Unassigned"),
        (4, "Ignored"),
        (5, "Removed")
    )

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
    person = models.ForeignKey(Person, on_delete=models.SET_DEFAULT, default=0, related_name="+")
    uncertainty = models.FloatField()
    status = models.PositiveIntegerField(choices=STATUS_OPTIONS)

    @staticmethod
    def get_eyes(face):
        """ Find eyes within a face

        Parameters
        ----------
        face : array
            The face (as an OpenCV pixel matrix)

        Returns
        -------
        list of eye or None
            The eyes found (in the format [(l_x, l_y), (r_x, r_y)]), or None if no valid pair found
        """

        global cascades

        height, width = face.shape[:2]

        # Detect all possible eyes
        both_eyes = [(e[0] + e[2] / 2, e[1] + e[3] / 2) for e in cascades["eye"].detectMultiScale(face, 1.1, 5, 0, (round(width / 6), round(height / 6)), (round(width / 4), round(height / 4)))]
        left_eyes = [(e[0] + e[2] / 2, e[1] + e[3] / 2) for e in cascades["left_eye"].detectMultiScale(face, 1.1, 5, 0, (round(width / 7), round(height / 7)), (round(width / 3), round(height / 3)))]
        right_eyes = [(e[0] + e[2] / 2, e[1] + e[3] / 2) for e in cascades["right_eye"].detectMultiScale(face, 1.1, 5, 0, (round(width / 7), round(height / 7)), (round(width / 3), round(height / 3)))]

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

    @staticmethod
    def choose_eye(all_eyes, side, width, height):
        """ Choose the best available eye for one side of a face

        Parameters
        ----------
        all_eyes : list of eye
            List of eyes (each in format (x, y))
        side : bool
            The side of the face to choose for (left - False, right - True)
        width : int
            Width of the whole face
        height : int
            Height of the whole face

        Returns
        -------
        eye or None
            The chosen eye, or None if no eye found on the correct side
        """

        for eye in all_eyes:
            eye_side = Face.get_eye_side(eye, width, height)
            if eye_side == side:
                return eye

        return None

    @staticmethod
    def get_eye_side(eye, width, height):
        """ Determine which side of the face an eye is on

        Eyes in top-left/bottom-right quadrants are considered left,
        and top-right/bottom-left are considered right. This method aims
        to detect upside-down faces.

        Parameters
        ----------
        eye : tuple of int
            The eye to test (in format (x, y))
        width : int
            Width of the whole face
        height : int
            Height of the whole face

        Returns
        -------
        bool
            The side of the face (left - False, right - True)
        """

        x = eye[0] - width / 2
        y = height / 2 - eye[1]

        return y / x < 0

    @staticmethod
    def get_rotation(eyes):
        """ Get the angle of rotation of a face from the eye positions

        Parameters
        ----------
        eyes : list of eye
            The eyes (in format [(l_x, l_y), (r_x, r_y)])

        Returns
        -------
        float
            The angle of rotation, in degrees
        """

        x_diff = eyes[0][0] - eyes[1][0]
        y_diff = eyes[0][1] - eyes[1][1]

        return math.degrees(math.atan(y_diff / x_diff))

    @staticmethod
    def recognize_faces():
        """ Recognise people in all faces in database, based on user-identified faces """

        utils.log("Recognising faces found previously")

        # Create face recognizer
        face_recognizer = cv2.face.LBPHFaceRecognizer_create(2, 16, 16, 16)
        untrained = True

        # Find user-identified faces
        known_faces = Face.objects.filter(person__id__gt=0, status__lt=3)
        print("Known faces:", len(known_faces))
        if len(known_faces) == 0:
            utils.log("No known faces found, not running recognition")
            return

        # Train the face recognizer using user-identified faces
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

        # Fetch unconfirmed faces
        unknown_faces = Face.objects.filter(status__lt=4, status__gt=1)
        print("Unknown faces:", len(unknown_faces))

        # Predict identities of unknown faces, and save to database
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

    def get_image(self, color, **kwargs):
        """ Extract this face from its image file

        Parameters
        ----------
        color : int
            OpenCV color encoding constant for Face output
        height : int, optional
            Height (pixels) for Face output

        Returns
        -------
        array
            The face, as an OpenCV pixel matrix
        """

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
            bbox_w *= scale
            bbox_h *= scale
        else:
            scaled_image = bbox_image

        # Rotate image
        M = cv2.getRotationMatrix2D((x, y), r, 1)
        rot_image = cv2.warpAffine(scaled_image, M, (cround(bbox_w), cround(bbox_h)))

        # Crop down to face
        face_image = rot_image[cround(y - h / 2): cround(y + h / 2), cround(x - w / 2): cround(x + w / 2)]

        return face_image


class GeoTagArea(models.Model):
    """ GeoTag area grouping model

    Geotags for multiple files associated with the same
    location/area should be grouped using this model.

    Attributes
    ----------
    name : TextField
        The (user-friendly) name of the location/area
    address : TextField
        The address of the location (centre of the area)
    latitude : FloatField
        The latitude co-ordinate of the centre of the area
    longitude : FloatField
        The longitude co-ordinate of the centre of the area
    radius : FloatField
        The radius of the area (TODO determine the unit this is in)
    date_created : DateTimeField
        The date upon which this area was created
    """

    name = models.TextField()
    address = models.TextField()
    latitude = models.FloatField()
    longitude = models.FloatField()
    radius = models.FloatField()
    # created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    date_created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class GeoTag(models.Model):
    """ GeoTag model for file locations

    Attributes
    ----------
    latitude : FloatField
        The latitude co-ordinate of the location (None if only an area is selected rather a specific point)
    longitude : FloatField
        The longitude co-ordinate of the location (None if only an area is selected rather a specific point)
    area : ForeignKey(GeoTagArea)
        The area grouping to which this geotag belongs (can be None)
    date_created : DateTimeField
        The date upon which this geotag was created
    """

    latitude = models.FloatField(null=True)
    longitude = models.FloatField(null=True)
    area = models.ForeignKey(GeoTagArea, on_delete=models.CASCADE, related_name="+", null=True)
    # created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+", null=True)
    date_created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return "%s, %s (%s)" % (round(self.latitude, 2), round(self.longitude, 2), self.area)

    @staticmethod
    def exif_to_degrees(values):
        """ Convert EXIF GPS co-ordinate to a single value (in degrees)

        Parameters
        ----------
        values : list of { num : str, den : str }
            EXIF-style co-ordinates, as [degrees, arcminutes, arcseconds].
            Each is a fraction stored as numerator and denominator.

        Returns
        -------
        float
            The co-ordinate in degrees
        """

        d = float(values[0].num) / float(values[0].den)
        m = float(values[1].num) / float(values[1].den)
        s = float(values[2].num) / float(values[2].den)

        return d + (m / 60.0) + (s / 3600.0)

    @staticmethod
    def from_exif(exif_data):
        """ Create a GeoTag instance from location information stored in EXIF data

        Parameters
        ----------
        exif_data : dict
            All EXIF data from a file

        Returns
        -------
        GeoTag or None
            A new GeoTag model instance, or None if no location data present
        """

        # Extract variables from dict
        exif_latitude = utils._get_if_exist(exif_data, ["GPS", "GPSLatitude"])
        exif_latitude_ref = utils._get_if_exist(exif_data, ["GPS", "GPSLatitudeRef"])
        exif_longitude = utils._get_if_exist(exif_data, ["GPS", "GPSLongitude"])
        exif_longitude_ref = utils._get_if_exist(exif_data, ["GPS", "GPSLongitudeRef"])

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
