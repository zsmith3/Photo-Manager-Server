# Generated by Django 3.1.2 on 2020-12-30 15:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fileserver', '0006_auto_20201227_1739'),
    ]

    operations = [
        migrations.AddField(
            model_name='face',
            name='encoding',
            field=models.BinaryField(null=True),
        ),
        migrations.AddField(
            model_name='historicalface',
            name='encoding',
            field=models.BinaryField(null=True),
        ),
    ]
