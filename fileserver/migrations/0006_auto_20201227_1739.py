# Generated by Django 3.1.2 on 2020-12-27 17:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fileserver', '0005_auto_20201007_1025'),
    ]

    operations = [
        migrations.AddField(
            model_name='file',
            name='notes',
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name='historicalfile',
            name='notes',
            field=models.TextField(null=True),
        ),
    ]
