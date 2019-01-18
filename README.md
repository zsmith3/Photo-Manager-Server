# Remote Photo Management System - File Server

This is the Django-based server for my photo management system. The client-side code can be found [here](https://github.com/zsmith3/Photo-Manager-Client/).


## Installation

`$variables` should be replaced with whatever names you want.

1) Install [Python](https://www.python.org/downloads/)
2) Install Django (`pip install django`)
3) Create a project (`django-admin startproject $projectname`) and enter it (`cd $projectname`)
4) Clone this repository (`git clone https://github.com/zsmith3/Photo-Manager-Server/ $appname`) and enter it (`cd $appname`)
5) Install dependencies (`pip install -r requirements.txt`)
6) Modify **$projectname/settings.py**:
	```python
	import datetime

	# ...

	INSTALLED_APPS = [
		"$appname.apps.FileserverConfig",
		"rest_framework",
		"rest_framework.authtoken",
		"rest_framework_filters",
		"corsheaders",
		"simple_history",
		# ...
	]

	MIDDLEWARE = [
    	"corsheaders.middleware.CorsMiddleware",
		"simple_history.middleware.HistoryRequestMiddleware",
		# ...
	]

	# ...

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
			"rest_framework_jwt.authentication.JSONWebTokenAuthentication",
		),
		"DEFAULT_FILTER_BACKENDS": (
			"rest_framework_filters.backends.RestFrameworkFilterBackend",
		)
	}

	JWT_AUTH = {
		"JWT_EXPIRATION_DELTA": datetime.timedelta(365)
	}

	CORS_ORIGIN_WHITELIST = (
		"localhost",
		"localhost:1234"  # for parcel-bundler development server
	)
	```
7) Modify **$projectname/urls.py**:
	```python
	urlpatterns = [
		path('$appurl/', include('$appname.urls'))
		# ...
	]
	```
8) Make migrations (`python manage.py makemigrations $appname`)
9) Run migrations (`python manage.py migrate`)
10) You should now be able to run the server with `python manage.py runserver`
11) Make an admin user (`python manage.py createsuperuser`)
12) (Currently) add a new RootFolder and User for testing using the admin page (*/admin*). Select a created RootFolder and use the options menu to scan the filesystem and update the database.
13) For production use (NOTE this is not production-ready yet), use any WSGI-supporting web server. I use [Apache](https://httpd.apache.org/), and recommend [using](https://httpd.apache.org/docs/2.4/ssl/ssl_howto.html) and [forcing](https://wiki.apache.org/httpd/RewriteHTTPToHTTPS) HTTPS. See [here](https://docs.djangoproject.com/en/2.1/howto/deployment/wsgi/modwsgi/) for instructions on hosting Django through Apache.


## Features

TODO


## Contributing

Any contribution would be welcomed and greatly appreciated, even if just in the form of suggestions/bug reports.
