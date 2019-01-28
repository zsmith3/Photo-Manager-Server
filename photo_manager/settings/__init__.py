import os

# Default settings (commited to git)
from .core import *

# Instance settings (not commited)
try:
    from .user import *
except ImportError:
    import random
    f = open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "user.py"), "w")
    chars = "abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)"
    SECRET_KEY = "".join(random.SystemRandom().choice(chars) for i in range(50))
    f.write(f"SECRET_KEY = \"{ SECRET_KEY }\"\n\n# Add your custom settings here (using standard django setting names)\n")
    f.close()

# Heroku settings
if "heroku" in os.environ:
    import django_heroku

    django_heroku.settings(locals())

# Settings for the Heroku-based public demo
if "heroku_demo" in os.environ:
    CORS_ORIGIN_ALLOW_ALL = True

    DEBUG = False

    # Download sample files (if not done yet)
    sample_files_dir = os.path.join(BASE_DIR, "sample_files")
    if not os.path.isdir(sample_files_dir):
        import zipfile
        from urllib import request
        zip_fn = "sample_files.zip"
        request.urlretrieve(os.environ["SAMPLE_ZIP_URL"], zip_fn)
        zip_ref = zipfile.ZipFile(zip_fn, "r")
        zip_ref.extractall(sample_files_dir)
        zip_ref.close()
        os.unlink(zip_fn)
