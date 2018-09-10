# Remote Photo Management System - Server branch

This branch contains Django-based code for hosting the server-side API. For more details on this project see the master branch README.

## Installation

NOTE: these instructions haven't been tested and are probably missing something.

1) Install:
	- [Django](https://www.djangoproject.com/)
	- [Django Rest Framework](http://www.django-rest-framework.org/)
		- [JSON WebToken Authentication for DRF](http://getblimp.github.io/django-rest-framework-jwt/)
		- [MessagePack for DRF](https://github.com/juanriaza/django-rest-framework-msgpack)
		- [QueryFields for DRF](https://github.com/wimglenn/djangorestframework-queryfields)
	- [OpenCV-Python](https://pypi.org/project/opencv-python/)
	- [OpenCV-Contrib-Python](https://pypi.org/project/opencv-contrib-python/)
	- [Pillow](https://python-pillow.org/) or [Pillow-SIMD](https://github.com/uploadcare/pillow-simd)
	- [ExifRead](https://pypi.org/project/ExifRead/)
	- [Mutagen](https://github.com/quodlibet/mutagen)
	- [Numpy](http://www.numpy.org/)
	- [Piexif](https://pypi.org/project/piexif/)
2) Create a new project and add the following settings:
	```python
	INSTALLED_APPS = [
		"fileserver.apps.FileserverConfig",
		"rest_framework",
		"rest_framework.authtoken",
		...
	]

	REST_FRAMEWORK = {
		"DEFAULT_RENDERER_CLASSES": (
			"rest_framework.renderers.JSONRenderer",
			"rest_framework_msgpack.renderers.MessagePackRenderer",
			"rest_framework.renderers.BrowsableAPIRenderer"
		),
		"DEFAULT_PARSER_CLASSES": (
			"rest_framework.parsers.JSONParser",
			"rest_framework_msgpack.parsers.MessagePackParser"
		),
		"DEFAULT_AUTHENTICATION_CLASSES": (
			"rest_framework_jwt.authentication.JSONWebTokenAuthentication"
		)
	}

	JWT_AUTH = {
		"JWT_EXPIRATION_DELTA": datetime.timedelta(365)
	}
	```
3) Create a new app (e.g. "fileserver") and paste all files from this branch into the new app
4) Add fileserver.urls to the main project urls file
5) See instructions in the web branch to host the static client-side files
	- Add Django to static server through WSGI (see [here](https://docs.djangoproject.com/en/2.1/howto/deployment/wsgi/modwsgi/) for Apache instructions)
