# Generated by Django 4.2.7 on 2024-06-13 12:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cplus_api', '0008_scenariotask_code_version'),
    ]

    operations = [
        migrations.AddField(
            model_name='scenariotask',
            name='stack_trace_errors',
            field=models.TextField(blank=True, null=True),
        ),
    ]
