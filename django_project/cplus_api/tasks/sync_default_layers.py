import logging
import os
import typing
import tempfile

import rasterio
from datetime import datetime
from django.utils import timezone

from celery import shared_task
from django.contrib.auth.models import User
from storages.backends.s3 import S3Storage
from django.conf import settings
from django.core.files.storage import FileSystemStorage

from cplus_api.models import (
    select_input_layer_storage,
    InputLayer,
    COMMON_LAYERS_DIR
)
from cplus_api.utils.api_helper import get_layer_type

logger = logging.getLogger(__name__)


class ProcessFile:
    """
    Class to process a file dictionary into an Input Layer

    :param storage: Django storage instance
    :type storage: FileSystemStorage or S3Storage

    :param owner: Owner of the input layer
    :type owner: User

    :param component_type: Component type of the input layer e.g. ncs_pathway
    :type component_type: str

    :param file: Dictionary of the file info to be processed
    :type file: dict

    :return: None
    :rtype: None
    """
    def __init__(
        self,
        storage: typing.Union[FileSystemStorage, S3Storage],
        owner: User,
        component_type: str,
        file: dict
    ):
        self.storage = storage
        self.owner = owner
        self.component_type = component_type
        self.file = file
        self.input_layer, self.created = InputLayer.objects.get_or_create(
            owner=owner,
            privacy_type=InputLayer.PrivacyTypes.COMMON,
            component_type=component_type,
            file=file['Key'],
            defaults={
                'created_on': timezone.now(),
                'layer_type': get_layer_type(file['Key'])
            }
        )

    def read_metadata(
        self,
        file_path: str
    ):
        """
        Read metadata from layer file and save it to InputLayer object

        :param file_path: path for input file
        :type file_path: str

        :return: None
        :rtype: None
        """
        with rasterio.open(file_path) as dataset:
            transform = dataset.transform
            res_x = abs(transform[0])
            res_y = abs(transform[4])
            crs = dataset.crs
            nodata = dataset.nodata
            unit = dataset.crs.units_factor[0]
            unit = "m" if unit == "metre" else unit

            metadata = {
                "is_raster": get_layer_type(self.file['Key']) == 0,
                "crs": str(crs),
                "resolution": [res_x, res_y],
                "unit": unit,
                "nodata_value": nodata,
                "is_geographic": dataset.crs.is_geographic
            }
            if not self.input_layer.name:
                self.input_layer.name = os.path.basename(self.file['Key'])
            if not self.input_layer.description:
                self.input_layer.description = (
                    os.path.basename(self.file['Key'])
                )
            self.input_layer.metadata = metadata
            self.input_layer.file.name = self.file['Key']
            self.input_layer.size = os.path.getsize(file_path)
            self.input_layer.save()

    def run(self):
        """
        Function to trigger file processing

        :return: None
        :rtype: None
        """
        # Save layer if the file is modified after input layers last saved OR
        # if input layer is a new record
        if (
                self.file['LastModified'] > self.input_layer.modified_on or
                self.created
        ):
            media_root = self.storage.location or settings.MEDIA_ROOT
            if isinstance(self.storage, FileSystemStorage):
                download_path = os.path.join(media_root, self.file['Key'])
                os.makedirs(os.path.dirname(download_path), exist_ok=True)
                self.read_metadata(download_path)
                os.remove(download_path)
            else:
                with tempfile.NamedTemporaryFile() as tmpfile:
                    boto3_client = self.storage.connection.meta.client
                    boto3_client.download_file(
                        self.storage.bucket_name,
                        self.file['Key'],
                        tmpfile.name,
                        Config=settings.AWS_TRANSFER_CONFIG
                    )
                    self.read_metadata(tmpfile.name)


@shared_task(name="sync_default_layers")
def sync_default_layers():
    """
    Create Input Layers from default layers copied to S3/local directory
    """

    storage = select_input_layer_storage()
    component_types = [c[0] for c in InputLayer.ComponentTypes.choices]
    admin_username = os.getenv('ADMIN_USERNAME')
    owner = User.objects.get(username=admin_username)
    if isinstance(storage, FileSystemStorage):
        media_root = storage.location or settings.MEDIA_ROOT
        for component_type in component_types:
            component_path = os.path.join(
                media_root, COMMON_LAYERS_DIR, component_type
            )
            os.makedirs(component_path, exist_ok=True)
            layers = os.listdir(component_path)
            for layer in layers:
                key = f"{COMMON_LAYERS_DIR}/{component_type}/{layer}"
                download_path = os.path.join(media_root, key)
                last_modified = datetime.fromtimestamp(
                    os.path.getmtime(download_path),
                    tz=timezone.now().tzinfo
                )
                file = {
                    "Key": key,
                    "LastModified": last_modified,
                    "Size": os.path.getsize(download_path)
                }
                ProcessFile(storage, owner, component_type, file).run()
    else:
        boto3_client = storage.connection.meta.client
        for component_type in component_types:
            response = boto3_client.list_objects(
                Bucket=storage.bucket_name,
                Prefix=f"{COMMON_LAYERS_DIR}/{component_type}"
            )
            for file in response.get('Contents', []):
                ProcessFile(storage, owner, component_type, file).run()
