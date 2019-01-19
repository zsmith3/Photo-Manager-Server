# Remote Photo Management System - File Server

This is the Django-based server for my photo management system. See [Photo-Manager-Client](https://github.com/zsmith3/Photo-Manager-Client/) for more information about the project, as well as the client-side code.


## Installation

1) Install [Python](https://www.python.org/downloads/) and [Powershell](https://docs.microsoft.com/en-us/powershell/scripting/install/installing-powershell?view=powershell-6)
2) Clone this repository (`git clone https://github.com/zsmith3/Photo-Manager-Server/`) and enter it (`cd Photo-Manager-Server`)
3) Run `powershell gen_settings.ps1` to generate a user settings file at *photo_manager/settings/user.py* with an auto-generated `SECRET_KEY`
4) Add any settings you want to change in *photo_manager/settings/user.py*. For example, I use PostgreSQL:
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
	Note that the default settings are intended for debugging, **NOT** production use.
5) Run Python module installation and database migrations using `powershell setup.ps1`. You will also be prompted to create a Django admin user.
6) For production use (NOTE this is not production-ready yet), use any WSGI-supporting web server. I use [Apache](https://httpd.apache.org/), and recommend [using](https://httpd.apache.org/docs/2.4/ssl/ssl_howto.html) and [forcing](https://wiki.apache.org/httpd/RewriteHTTPToHTTPS) HTTPS. See [here](https://docs.djangoproject.com/en/2.1/howto/deployment/wsgi/modwsgi/) for instructions on hosting Django through Apache.


## Usage

1) Having followed the installation steps above, you should now be able to run the server with `python manage.py runserver`
2) (Currently) add a new RootFolder using the admin page (*/admin*). Select a created RootFolder and use the options menu to scan the filesystem and update the database.


## Contributing

Any contribution would be welcomed and greatly appreciated, even if just in the form of suggestions/bug reports.
