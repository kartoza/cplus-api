import logging
import os
import typing

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


def process_file(
        storage: typing.Union[FileSystemStorage, S3Storage],
        owner: User,
        component_type: str,
        file: dict
):
    """
    Function to process a file dictionary into an Input Layer
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
    input_layer, created = InputLayer.objects.get_or_create(
        name=os.path.basename(file['Key']),
        owner=owner,
        privacy_type=InputLayer.PrivacyTypes.COMMON,
        component_type=component_type,
        defaults={
            'created_on': timezone.now(),
            'layer_type': get_layer_type(file['Key'])
        }
    )

    # Save layer if the file is modified after input layers last saved OR
    # if input layer is a new record
    if file['LastModified'] > input_layer.modified_on or created:
        media_root = storage.location or settings.MEDIA_ROOT
        download_path = os.path.join(media_root, file['Key'])
        os.makedirs(os.path.dirname(download_path), exist_ok=True)

        if not isinstance(storage, FileSystemStorage):
            boto3_client = storage.connection.meta.client
            boto3_client.download_file(
                storage.bucket_name,
                file['Key'],
                download_path,
                Config=settings.AWS_TRANSFER_CONFIG
            )
        with rasterio.open(download_path) as dataset:
            transform = dataset.transform
            res_x = abs(transform[0])
            res_y = abs(transform[4])
            crs = dataset.crs
            nodata = dataset.nodata

            metadata = {
                "name": os.path.basename(download_path),
                "is_raster": get_layer_type(download_path) == 0,
                "description": os.path.basename(download_path),
                "crs": str(crs),
                "resolution": [res_x, res_y],
                "no_data": nodata
            }
            input_layer.metadata = metadata
            input_layer.file.name = file['Key']
            input_layer.save()
            if not isinstance(storage, FileSystemStorage):
                os.remove(download_path)


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
                process_file(storage, owner, component_type, file)

    else:
        boto3_client = storage.connection.meta.client
        for component_type in component_types:
            response = boto3_client.list_objects(
                Bucket=storage.bucket_name,
                Prefix=f"{COMMON_LAYERS_DIR}/{component_type}"
            )
            for file in response.get('Contents', []):
                process_file(storage, owner, component_type, file)
