# Generated by Django 4.2.7 on 2024-08-19 06:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cplus_api', '0009_scenariotask_stack_trace_errors'),
    ]

    operations = [
        migrations.AddField(
            model_name='inputlayer',
            name='metadata',
            field=models.JSONField(blank=True, default=dict, help_text='Layer Metadata.'),
        ),
    ]
