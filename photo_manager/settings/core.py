import os
import datetime

DEBUG = True

# The API permissions class will authorise all requests in DEBUG mode
# Set this variable to True if you want to disable this behaviour
USE_AUTH_IN_DEBUG = False

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

INSTALLED_APPS = [
    "fileserver.apps.FileserverConfig",
    "rest_framework",
    "rest_framework.authtoken",
    "rest_framework_filters",
    "corsheaders",
    "simple_history",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "photo_manager.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "photo_manager.wsgi.application"

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": os.path.join(BASE_DIR, "db.sqlite3")}}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-gb"

TIME_ZONE = "UTC"

USE_L10N = True

STATIC_URL = "/static/"

STATIC_ROOT = os.path.join(BASE_DIR, "static")

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer", "rest_framework_msgpack.renderers.MessagePackRenderer", "rest_framework.renderers.BrowsableAPIRenderer"),
    "DEFAULT_PARSER_CLASSES": ("rest_framework.parsers.JSONParser", "rest_framework_msgpack.parsers.MessagePackParser"),
    "DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_jwt.authentication.JSONWebTokenAuthentication", ),
    "DEFAULT_FILTER_BACKENDS": ("rest_framework_filters.backends.RestFrameworkFilterBackend", )
}

JWT_AUTH = {"JWT_EXPIRATION_DELTA": datetime.timedelta(365)}

CORS_ORIGIN_WHITELIST = ("https://localhost", "http://localhost:1234")

PYTHON_LOG_MAX_LINES = 100000
