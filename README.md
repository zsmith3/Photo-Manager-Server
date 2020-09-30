# Remote Photo Management System - File Server

[![Build Status](https://travis-ci.com/zsmith3/Photo-Manager-Server.svg?branch=master)](https://travis-ci.com/zsmith3/Photo-Manager-Server)

This is the Django-based server for my photo management system. See [Photo-Manager-Client](https://github.com/zsmith3/Photo-Manager-Client/) for more information about the project, as well as the client-side code.


## Installation

1) Install [Python](https://www.python.org/downloads/) and [CMake](https://cmake.org/download/).
2) Clone this repository (`git clone https://github.com/zsmith3/Photo-Manager-Server/`) and enter it (`cd Photo-Manager-Server`)
3) Install dependencies and collect static files:
	- `pip install -r requirements.txt`
	- `python manage.py collectstatic`
4) This will have auto-generated a user-specific settings file at *./photo_manager/settings/user.py*, with a random `SECRET_KEY`. You should add any custom settings you want to this file. For example, I use PostgreSQL:
	```python
	DATABASES = {
		"default": {
			"ENGINE": "django.db.backends.postgresql",
			"HOST": "localhost",
			"PORT": "5432",
			"NAME": "postgres",
			"USER": "postgres",
			"PASSWORD": "password"
		}
	}
	```
5) Now perform database migrations:
	- `python manage.py makemigrations`
	- `python manage.py makemigrations fileserver`
	- `python manage.py migrate`
	- `python manage.py createsuperuser` (optional)
6) For production use (NOTE this is not production-ready yet), use any WSGI-supporting web server. I use [Apache](https://httpd.apache.org/), and recommend [using](https://httpd.apache.org/docs/2.4/ssl/ssl_howto.html) and [forcing](https://wiki.apache.org/httpd/RewriteHTTPToHTTPS) HTTPS. See [here](https://docs.djangoproject.com/en/2.1/howto/deployment/wsgi/modwsgi/) for instructions on hosting Django through Apache.


## Usage

1) Having followed the installation steps above, you should now be able to run the server with `python manage.py runserver`
2) (Currently) add a new RootFolder using the admin page (*/admin*). Select a created RootFolder and use the options menu to scan the filesystem and update the database.

This codebase uses YAPF for formatting - use the following command to auto-format all files:

`yapf --in-place --recursive --style='{column_limit: 180}' --exclude='**/migrations/**' .`


## Contributing

Any contribution would be welcomed and greatly appreciated, even if just in the form of suggestions/bug reports.
