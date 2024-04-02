# Generated by Django 4.2.7 on 2024-03-01 16:12

import core.models.preferences
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='SitePreferences',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('site_title', models.CharField(default='CPLUS API', max_length=512)),
                ('api_config', models.JSONField(blank=True, default=core.models.preferences.default_api_config, help_text='API pagination configuration.')),
            ],
            options={
                'verbose_name_plural': 'site preferences',
            },
        ),
    ]