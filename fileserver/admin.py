from django.contrib import admin
from django.utils.html import format_html
from simple_history.admin import SimpleHistoryAdmin

import threading

from . import models

admin.site.register(models.AuthGroup)
admin.site.register(models.UserConfig)


def get_files(modeladmin, request, queryset):
    """ Detect new/moved files in the local filesystem """

    threads = []
    for folder in queryset:
        threads.append(threading.Thread(target=folder.scan_filesystem))
    for thread in threads:
        thread.start()
    modeladmin.message_user(request, format_html("Began scanning %s root folders. See <a href='/admin/logs'>here</a> for details." % len(queryset)))


get_files.short_description = "Scan the filesystem for new files"


def clear_files(modeladmin, request, queryset):
    """ Detect file deletions in the local filesystem """

    threads = []
    for folder in queryset:
        threads.append(threading.Thread(target=folder.prune_database))
    for thread in threads:
        thread.start()
    modeladmin.message_user(request, format_html("Began pruning %s root folders. See <a href='/admin/logs'>here</a> for details." % len(queryset)))


clear_files.short_description = "Prune deleted files from the database"


def get_faces(modeladmin, request, queryset):
    """ Detect faces in image files """

    threads = []
    for folder in queryset:
        threads.append(threading.Thread(target=folder.detect_faces))
    for thread in threads:
        thread.start()
    modeladmin.message_user(request, format_html("Began scanning files in %s root folders for faces. See <a href='/admin/logs'>here</a> for details." % len(queryset)))


get_faces.short_description = "Detect faces in files"


def recognize_faces(modeladmin, request, queryset):
    """ Recognize faces as people """

    thread = threading.Thread(target=models.Face.recognize_faces)
    thread.start()
    modeladmin.message_user(request, format_html("Began predicting identities of all faces in database. See <a href='/admin/logs'>here</a> for details."))


recognize_faces.short_description = "Recognize (all) faces in database"


def update_database(modeladmin, request, queryset):
    """ Run all fileserver database updates """

    threads = []
    for folder in queryset:
        threads.append(threading.Thread(target=folder.update_database))
    for thread in threads:
        thread.start()
    modeladmin.message_user(request, format_html("Began updating the database for %s root folders. See <a href='/admin/logs'>here</a> for details." % len(queryset)))


# TODO remove threads, different folders should be handled sequentially
# and ideally avoid repeating face-recognition when multiple folders selected

update_database.short_description = "Update all aspects of the database"


class RootFolderAdmin(SimpleHistoryAdmin):
    """ Admin actions for fileserver database management, attached to RootFolder """

    actions = [get_files, clear_files, get_faces, recognize_faces, update_database]


admin.site.register(models.RootFolder, RootFolderAdmin)

admin.site.register(models.Folder, SimpleHistoryAdmin)

admin.site.register(models.Album, SimpleHistoryAdmin)

admin.site.register(models.AlbumFile, SimpleHistoryAdmin)

admin.site.register(models.PersonGroup, SimpleHistoryAdmin)

admin.site.register(models.Person, SimpleHistoryAdmin)

admin.site.register(models.File, SimpleHistoryAdmin)

admin.site.register(models.Face, SimpleHistoryAdmin)

admin.site.register(models.GeoTagArea, SimpleHistoryAdmin)

admin.site.register(models.GeoTag, SimpleHistoryAdmin)
