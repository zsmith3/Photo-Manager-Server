release: python manage.py makemigrations && python manage.py migrate && python manage.py makemigrations fileserver && python manage.py migrate
web: gunicorn photo_manager.wsgi
