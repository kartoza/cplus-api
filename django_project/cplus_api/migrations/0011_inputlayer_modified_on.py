# Generated by Django 4.2.7 on 2024-08-28 12:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cplus_api', '0010_inputlayer_metadata'),
    ]

    operations = [
        migrations.AddField(
            model_name='inputlayer',
            name='modified_on',
            field=models.DateTimeField(auto_now=True),
        ),
    ]