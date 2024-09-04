import os
import uuid
import shutil
from zipfile import ZipFile
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.utils import timezone
from django.core.files.storage import storages, FileSystemStorage


COMMON_LAYERS_DIR = 'common_layers'
INTERNAL_LAYERS_DIR = 'internal_layers'


def input_layer_dir_path(instance, filename):
    """Return upload directory path for Input Layer."""
    file_path = f'{str(instance.owner.pk)}/'
    if instance.privacy_type == InputLayer.PrivacyTypes.COMMON:
        file_path = f'{COMMON_LAYERS_DIR}/'
    if instance.privacy_type == InputLayer.PrivacyTypes.INTERNAL:
        file_path = f'{INTERNAL_LAYERS_DIR}/'
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


def default_output_meta():
    """
    Default value for OutputLayer's output_meta.
    """
    return {}


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
        SNAP_LAYER = 'snap_layer', _('snap_layer')
        SIEVE_MASK_LAYER = 'sieve_mask_layer', _('sieve_mask_layer')
        MASK_LAYER = 'mask_layer', _('mask_layer')

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

    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text='Layer Metadata.'
    )

    modified_on = models.DateTimeField(auto_now=True)

    description = models.TextField(
        null=False,
        blank=True,
        default=''
    )

    def __str__(self):
        return f"{self.name} - {self.component_type}"

    def download_to_working_directory(self, base_dir: str):
        if not self.is_available():
            return None
        dir_path: str = os.path.join(
            base_dir,
            self.component_type
        )
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        file_path: str = os.path.join(
            dir_path,
            os.path.basename(self.file.name)
        )
        storage = select_input_layer_storage()
        if isinstance(storage, FileSystemStorage):
            with open(file_path, 'wb+') as destination:
                for chunk in self.file.chunks():
                    destination.write(chunk)
        else:
            boto3_client = storage.connection.meta.client
            boto3_client.download_file(
                storage.bucket_name,
                self.file.name,
                file_path,
                Config=settings.AWS_TRANSFER_CONFIG
            )
        self.last_used_on = timezone.now()
        self.save(update_fields=['last_used_on'])
        if file_path.endswith('.zip'):
            extract_path = os.path.join(
                dir_path,
                os.path.basename(file_path).replace('.zip', '_zip')
            )
            with ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
            shapefile = [
                file for file in os.listdir(extract_path)
                if file.endswith('.shp')
            ]
            if shapefile:
                return os.path.join(extract_path, shapefile[0])
            else:
                return None
        return file_path

    def is_available(self):
        if not self.file.name:
            return False
        return self.file.storage.exists(self.file.name)

    def is_in_correct_directory(self):
        layer_path = self.file.name
        prefix_path = f'{str(self.owner.pk)}/'
        if self.privacy_type == InputLayer.PrivacyTypes.COMMON:
            prefix_path = f'{COMMON_LAYERS_DIR}/'
        elif self.privacy_type == InputLayer.PrivacyTypes.INTERNAL:
            prefix_path = f'{INTERNAL_LAYERS_DIR}/'
        return layer_path.startswith(prefix_path)

    def fix_layer_metadata(self):
        if not self.is_available():
            return
        self.size = self.file.size
        self.save(update_fields=['size'])
        if self.is_in_correct_directory():
            return
        old_path = self.file.name
        correct_path = input_layer_dir_path(self, self.name)
        storage = select_input_layer_storage()
        if isinstance(storage, FileSystemStorage):
            full_correct_path = os.path.join(storage.location, correct_path)
            dirname = os.path.split(full_correct_path)[0]
            os.makedirs(dirname, exist_ok=True)
            shutil.move(
                os.path.join(storage.location, old_path),
                full_correct_path,
            )
        else:
            boto3_client = storage.connection.meta.client
            copy_source = {
                'Bucket': storage.bucket_name,
                'Key': old_path
            }
            boto3_client.copy(copy_source, storage.bucket_name, correct_path)
            boto3_client.delete_object(
                Bucket=storage.bucket_name, Key=old_path)
        self.file.name = correct_path
        self.save(update_fields=['file'])


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
    output_meta = models.JSONField(
        default=default_output_meta,
        blank=True,
        help_text='Output Metadata.'
    )

    def __str__(self):
        return f"{self.name} - {self.group} - {self.uuid}"


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
