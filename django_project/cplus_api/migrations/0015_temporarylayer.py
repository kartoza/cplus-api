# Generated by Django 4.2.7 on 2024-12-06 18:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cplus_api', '0014_alter_inputlayer_component_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='TemporaryLayer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file_name', models.CharField(help_text='File name that is stored in TEMPORARY_LAYER_DIR.', max_length=512)),
                ('size', models.IntegerField()),
                ('created_on', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
