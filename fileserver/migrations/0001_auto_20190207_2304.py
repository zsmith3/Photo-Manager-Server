# Generated by Django 2.1.3 on 2019-02-07 23:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fileserver', 'setup_data'),
    ]

    operations = [
        migrations.AlterField(
            model_name='file',
            name='length',
            field=models.BigIntegerField(),
        ),
        migrations.AlterField(
            model_name='historicalfile',
            name='length',
            field=models.BigIntegerField(),
        ),
    ]
