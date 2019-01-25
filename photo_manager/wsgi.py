"""
WSGI config for photo_manager project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/2.1/howto/deployment/wsgi/
"""

print("WSGI started")

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'photo_manager.settings')

print("Get WSGI application")

application = get_wsgi_application()

print("Got application")
