pip install -r requirements.txt
python manage.py makemigrations
python manage.py makemigrations fileserver
python manage.py migrate

Write-Output "Create Superuser for Django Admin system:"
python manage.py createsuperuser
