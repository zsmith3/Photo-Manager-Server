from django.db import migrations


# Create default AuthGroup models
def create_auth_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    AuthGroup = apps.get_model('fileserver', 'AuthGroup')

    users_group = Group.objects.create(name='Fileserver Users')
    AuthGroup.objects.create(id=1, group=users_group)

    admins_group = Group.objects.create(name='Fileserver Admins')
    AuthGroup.objects.create(id=2, group=admins_group)


# Create null Person and PersonGroup
def create_null_person(apps, schema_editor):
    PersonGroup = apps.get_model('fileserver', 'PersonGroup')
    PersonGroup.objects.create(id=0, name='Ungrouped')

    Person = apps.get_model('fileserver', 'Person')
    Person.objects.create(id=0, full_name='Unknown Person')


class Migration(migrations.Migration):

    dependencies = [
        ('fileserver', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_auth_groups),
        migrations.RunPython(create_null_person)
    ]
