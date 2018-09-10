from django.contrib import admin
from django.utils.html import format_html

import threading

from .models import *

admin.site.register(AuthGroup)
admin.site.register(UserConfig)


def get_files(modeladmin, request, queryset):
    threads = []
    for folder in queryset:
        threads.append(threading.Thread(target=folder.scan_filesystem))
    for thread in threads:
        thread.start()
    modeladmin.message_user(request, format_html("Began scanning %s root folders. See <a href='/admin/python_log'>here</a> for details." % len(queryset)))
get_files.short_description = "Scan the filesystem for new files"


def clear_files(modeladmin, request, queryset):
    threads = []
    for folder in queryset:
        threads.append(threading.Thread(target=folder.prune_database))
    for thread in threads:
        thread.start()
    modeladmin.message_user(request, format_html("Began pruning %s root folders. See <a href='/admin/python_log'>here</a> for details." % len(queryset)))
clear_files.short_description = "Prune deleted files from the database"


def get_faces(modeladmin, request, queryset):
    threads = []
    for folder in queryset:
        threads.append(threading.Thread(target=folder.detect_faces))
    for thread in threads:
        thread.start()
    modeladmin.message_user(request, format_html("Began scanning files in %s root folders for faces. See <a href='/admin/python_log'>here</a> for details." % len(queryset)))
get_faces.short_description = "Detect faces in files"


def recognize_faces(modeladmin, request, queryset):
    thread = threading.Thread(target=Face.recognize_faces)
    thread.start()
    modeladmin.message_user(request, format_html("Began predicting identities of all faces in database. See <a href='/admin/python_log'>here</a> for details."))
recognize_faces.short_description = "Recognize (all) faces in database"


def update_database(modeladmin, request, queryset):
    threads = []
    for folder in queryset:
        threads.append(threading.Thread(target=folder.update_database))
    for thread in threads:
        thread.start()
    modeladmin.message_user(request, format_html("Began updating the database for %s root folders. See <a href='/admin/python_log'>here</a> for details." % len(queryset)))
update_database.short_description = "Update all aspects of the database"


class RootAdmin(admin.ModelAdmin):
    actions = [get_files, clear_files, get_faces, recognize_faces, update_database]

admin.site.register(RootFolder, RootAdmin)

admin.site.register(Folder)

admin.site.register(Album)

admin.site.register(AlbumFile)

admin.site.register(PersonGroup)

admin.site.register(Person)

admin.site.register(File)

admin.site.register(Face)

admin.site.register(GeoTagArea)

admin.site.register(GeoTag)
