import os
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.utils import timezone
from django.core.files.storage import storages


def input_layer_dir_path(instance, filename):
    """Return upload directory path for Input Layer."""
    file_path = f'{str(instance.owner.pk)}/'
    if instance.privacy_type == InputLayer.PrivacyTypes.COMMON:
        file_path = 'common_layers/'
    if instance.privacy_type == InputLayer.PrivacyTypes.INTERNAL:
        file_path = 'internal_layers/'
    file_path = file_path + f'{instance.component_type}/' + filename
    return file_path


def output_layer_dir_path(instance, filename):
    """Return upload directory path for Output Layer."""
    file_path = f'{str(instance.owner.pk)}/{str(instance.scenario.uuid)}/'
    if not instance.is_final_output:
        file_path = file_path + f'{instance.group}/'
    file_path = file_path + filename
    return file_path


def select_input_layer_storage():
    """Return storage for input layer."""
    return storages['input_layer_storage']


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
        REFERENCE_LAYER = 'reference_layer', _('reference_layer')

    class PrivacyTypes(models.TextChoices):
        PRIVATE = 'private', _('private')
        INTERNAL = 'internal', _('internal')
        COMMON = 'common', _('common')

    file = models.FileField(
        upload_to=input_layer_dir_path,
        storage=select_input_layer_storage
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

    client_id = models.TextField(
        null=True,
        blank=True
    )

    def download_to_working_directory(self, base_dir):
        if not self.is_available():
            return None
        dir_path = os.path.join(
            base_dir,
            self.component_type
        )
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        file_path = os.path.join(
            dir_path,
            os.path.basename(self.file.name)
        )
        with open(file_path, 'wb+') as destination:
            for chunk in self.file.chunks():
                destination.write(chunk)
        self.last_used_on = timezone.now()
        self.save(update_fields=['last_used_on'])
        return file_path

    def is_available(self):
        if not self.file.name:
            return False
        return self.file.storage.exists(self.file.name)


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


class MultipartUpload(models.Model):
    """Model to store id of multipart upload."""

    upload_id = models.CharField(
        max_length=512
    )

    input_layer_uuid = models.UUIDField()

    created_on = models.DateTimeField()

    uploader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    parts = models.IntegerField()

    is_aborted = models.BooleanField(
        default=False
    )

    aborted_on = models.DateTimeField(
        null=True,
        blank=True
    )
