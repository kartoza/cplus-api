# Generated by Django 4.2.7 on 2024-08-30 07:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cplus_api', '0011_inputlayer_modified_on'),
    ]

    operations = [
        migrations.AddField(
            model_name='inputlayer',
            name='description',
            field=models.TextField(blank=True, default=''),
        ),
    ]