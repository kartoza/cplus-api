# Generated by Django 4.2.7 on 2024-05-09 03:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cplus_api', '0006_merge_20240508_0731'),
    ]

    operations = [
        migrations.AlterField(
            model_name='inputlayer',
            name='component_type',
            field=models.CharField(choices=[('ncs_pathway', 'ncs_pathway'), ('ncs_carbon', 'ncs_carbon'), ('priority_layer', 'priority_layer'), ('snap_layer', 'snap_layer'), ('sieve_mask_layer', 'sieve_mask_layer'), ('mask_layer', 'mask_layer')], max_length=255),
        ),
    ]
