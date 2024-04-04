from django.db import models
import uuid
from django.utils.translation import gettext_lazy as _
from django.conf import settings


def input_layer_dir_path(instance, filename):
    file_path = f'{str(instance.owner.pk)}/'
    if instance.privacy_type == InputLayer.PrivacyTypes.COMMON:
        file_path = 'common_layers/'
    if instance.privacy_type == InputLayer.PrivacyTypes.INTERNAL:
        file_path = 'internal_layers/'
    file_path = file_path + f'{instance.component_type}/' + filename
    return file_path


def output_layer_dir_path(instance, filename):
    file_path = f'{str(instance.owner.pk)}/{str(instance.scenario.uuid)}/'
    if not instance.is_final_output:
        file_path = file_path + f'{instance.group}/'
    file_path = file_path + filename
    return file_path


class BaseLayer(models.Model):
    class LayerTypes(models.IntegerChoices):
        RASTER = 0, _('Raster')
        VECTOR = 1, _('Vector')
        UNDEFINED = -1, _('Undefined')

    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True
    )

    name = models.CharField(
        max_length=512
    )

    created_on = models.DateTimeField()

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )

    layer_type = models.IntegerField(choices=LayerTypes.choices)

    size = models.IntegerField(
        null=True,
        blank=True,
        default=0
    )

    class Meta:
        abstract = True


class InputLayer(BaseLayer):
    class ComponentTypes(models.TextChoices):
        NCS_PATHWAY = 'ncs_pathway', _('ncs_pathway')
        NCS_CARBON = 'ncs_carbon', _('ncs_carbon')
        PRIORITY_LAYER = 'priority_layer', _('priority_layer')

    class PrivacyTypes(models.TextChoices):
        PRIVATE = 'private', _('private')
        INTERNAL = 'internal', _('internal')
        COMMON = 'common', _('common')

    file = models.FileField(
        upload_to=input_layer_dir_path
    )

    component_type = models.CharField(
        max_length=255,
        choices=ComponentTypes.choices
    )

    privacy_type = models.CharField(
        max_length=255,
        choices=PrivacyTypes.choices,
        default=PrivacyTypes.PRIVATE
    )

    last_used_on = models.DateTimeField(
        null=True,
        blank=True
    )


class OutputLayer(BaseLayer):

    is_final_output = models.BooleanField(
        default=False
    )

    group = models.CharField(
        max_length=256,
        null=True,
        blank=True
    )

    scenario = models.ForeignKey(
        'cplus_api.ScenarioTask',
        related_name='output_layers',
        on_delete=models.CASCADE
    )

    file = models.FileField(
        upload_to=output_layer_dir_path
    )

    is_deleted = models.BooleanField(
        default=False
    )
