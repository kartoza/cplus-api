# Generated by Django 4.2.7 on 2024-10-08 12:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cplus_api', '0012_inputlayer_description'),
    ]

    operations = [
        migrations.AddField(
            model_name='inputlayer',
            name='source',
            field=models.CharField(choices=[('cplus', 'CPLUS'), ('naturebase', 'Naturebase')], default='cplus', max_length=50),
        ),
    ]
