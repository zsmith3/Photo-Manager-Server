from django.contrib import admin
from django.utils.html import format_html
from simple_history.admin import SimpleHistoryAdmin

import threading

from . import models

admin.site.register(models.AuthGroup)
admin.site.register(models.UserConfig)


def update_files(modeladmin, request, queryset):
    threading.Thread(target=lambda: [folder.scan_filesystem() for folder in queryset]).start()
    modeladmin.message_user(request, format_html("Began scanning %s root folders. See <a href='/admin/logs'>here</a> for details." % len(queryset)))


update_files.short_description = "Scan for new files/clear deleted files"


def get_faces(modeladmin, request, queryset):
    threading.Thread(target=lambda: [folder.detect_faces() for folder in queryset]).start()
    modeladmin.message_user(request, format_html("Began scanning files in %s root folders for faces. See <a href='/admin/logs'>here</a> for details." % len(queryset)))


get_faces.short_description = "Detect faces in files"


def recognize_faces(modeladmin, request, queryset):
    threading.Thread(target=models.Face.recognize_faces).start()
    modeladmin.message_user(request, format_html("Began predicting identities of all faces in database. See <a href='/admin/logs'>here</a> for details."))


recognize_faces.short_description = "Recognize (all) faces in database"


def update_database(modeladmin, request, queryset):
    threading.Thread(target=lambda: [folder.update_database() for folder in queryset]).start()
    modeladmin.message_user(request, format_html("Began updating the database for %s root folders. See <a href='/admin/logs'>here</a> for details." % len(queryset)))


update_database.short_description = "Update all aspects of the database"


class RootFolderAdmin(SimpleHistoryAdmin):
    actions = [update_files, get_faces, recognize_faces, update_database]


def update_scans(modeladmin, request, queryset):
    threading.Thread(target=lambda: [folder.update_database() for folder in queryset]).start()
    modeladmin.message_user(request, format_html("Began searching %s root folders for scan files. See <a href='/admin/logs'>here</a> for details." % len(queryset)))


update_scans.short_description = "Update scan files listed in database"


class ScanRootFolderAdmin(SimpleHistoryAdmin):
    actions = [update_scans]


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

admin.site.register(models.ScanRootFolder, ScanRootFolderAdmin)

admin.site.register(models.ScanFolder, SimpleHistoryAdmin)

admin.site.register(models.Scan, SimpleHistoryAdmin)
