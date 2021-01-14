# Generated by Django 3.1.2 on 2021-01-13 15:20

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('fileserver', '0008_merge_20210107_1646'),
    ]

    operations = [
        migrations.AddField(
            model_name='file',
            name='access_group',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='fileserver.authgroup'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='folder',
            name='access_group',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='fileserver.authgroup'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='historicalfile',
            name='access_group',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='fileserver.authgroup'),
        ),
        migrations.AddField(
            model_name='historicalfolder',
            name='access_group',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='fileserver.authgroup'),
        ),
    ]