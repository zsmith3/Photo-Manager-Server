# Generated by Django 3.1.2 on 2022-12-27 11:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fileserver', '0012_authgroup_can_link'),
    ]

    operations = [
        migrations.AddField(
            model_name='album',
            name='access_groups',
            field=models.ManyToManyField(related_name='_album_access_groups_+', to='fileserver.AuthGroup'),
        ),
        migrations.AddField(
            model_name='person',
            name='access_groups',
            field=models.ManyToManyField(related_name='_person_access_groups_+', to='fileserver.AuthGroup'),
        ),
        migrations.AddField(
            model_name='persongroup',
            name='access_groups',
            field=models.ManyToManyField(related_name='_persongroup_access_groups_+', to='fileserver.AuthGroup'),
        ),
        migrations.AddField(
            model_name='scan',
            name='access_groups',
            field=models.ManyToManyField(related_name='_scan_access_groups_+', to='fileserver.AuthGroup'),
        ),
        migrations.AddField(
            model_name='scanfolder',
            name='access_groups',
            field=models.ManyToManyField(related_name='_scanfolder_access_groups_+', to='fileserver.AuthGroup'),
        ),
    ]