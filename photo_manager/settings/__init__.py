print("Settings file")

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
