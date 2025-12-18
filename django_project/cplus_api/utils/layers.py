import os
import tempfile

import typing
from pathlib import Path
from datetime import datetime
from zipfile import ZipFile

import rasterio
import requests
from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.storage import FileSystemStorage
from django.db.models import Q
from django.utils import timezone
from django.utils.html import strip_tags
from rasterio.errors import RasterioIOError
from requests.exceptions import HTTPError
from sentry_sdk import capture_exception
from storages.backends.s3 import S3Storage

from cplus_api.models import (
    select_input_layer_storage,
    InputLayer,
    COMMON_LAYERS_DIR
)
from cplus_api.utils.api_helper import get_layer_type, download_file


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
        file: typing.Dict,
        source: str = InputLayer.LayerSources.CPLUS,
    ):
        self.storage = storage
        self.owner = owner
        self.component_type = component_type
        self.file = file
        self.source = source
        if source == InputLayer.LayerSources.CPLUS:
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
        else:
            self.input_layer, self.created = InputLayer.objects.get_or_create(
                owner=owner,
                privacy_type=InputLayer.PrivacyTypes.COMMON,
                component_type=component_type,
                name=file['title'],
                defaults={
                    'created_on': timezone.now(),
                    'layer_type': get_layer_type(file['Key']),
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
        new_nodata_value = -9999
        with rasterio.open(file_path) as dataset:
            profile = dataset.profile

            # Set the new nodata value in the profile
            profile.update(nodata=new_nodata_value, dtype='float32')

            with tempfile.NamedTemporaryFile() as tmpfile:
                file_path = tmpfile.name

                # Write the output raster with the updated nodata value
                with rasterio.open(file_path, "w", **profile) as dst:
                    # Iterate over blocks using block_windows
                    for idx, window in dataset.block_windows():
                        # Read the data for the current block
                        block_data = dataset.read(window=window)
                        block_data = block_data.astype('float32')

                        # Replace nodata values in the block
                        block_data[block_data == dataset.nodata] = (
                            new_nodata_value
                        )

                        # Write the modified block to the output file
                        dst.write(block_data, window=window)

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
                    if not self.input_layer.name or self.input_layer.name == 'N/A':  # noqa
                        if self.source == InputLayer.LayerSources.CPLUS:
                            self.input_layer.name = os.path.basename(self.file['Key'])  # noqa
                        elif self.source == InputLayer.LayerSources.NATURE_BASE:  # noqa
                            self.input_layer.name = strip_tags(self.file['title'])  # noqa
                    if not self.input_layer.description:
                        if self.source == InputLayer.LayerSources.CPLUS:
                            self.input_layer.description = strip_tags(
                                os.path.basename(self.file['Key'])
                            )
                        elif self.source == InputLayer.LayerSources.NATURE_BASE:  # noqa
                            self.input_layer.description = strip_tags(
                                self.file['short_summary']
                            ).replace('&nbsp;', '')
                    self.input_layer.metadata = metadata

                    if self.source == InputLayer.LayerSources.NATURE_BASE:
                        self.input_layer.layer_type = 0
                    else:
                        self.input_layer.file.name = self.file['Key']

                    self.input_layer.size = os.path.getsize(file_path)
                    with open(file_path, 'rb') as layer:
                        storage = select_input_layer_storage()
                        if self.input_layer.file:
                            try:
                                os.remove(
                                    os.path.join(
                                        storage.location,
                                        self.input_layer.file.name
                                    )
                                )
                            except OSError:
                                pass
                        self.input_layer.file.save(
                            os.path.basename(self.file['Key']),
                            layer
                        )
                    self.input_layer.source = self.source
                    self.input_layer.action = self.file['action']
                    self.input_layer.save()

    def handle_nature_base(self, file_path):
        try:
            download_file(self.file['url'], file_path)
        except HTTPError as e:
            capture_exception(e)
            return
        zip_path = file_path
        if self.file['url'].endswith('.zip'):
            with ZipFile(zip_path, 'r') as zip_ref:
                tmpdir = tempfile.mkdtemp()
                zip_ref.extractall(tmpdir)
                tif_file = [
                    f for f in os.listdir(tmpdir) if
                    f.endswith('.tif') or f.endswith('.tiff')
                ]
                if tif_file:
                    self.file['Key'] = tif_file[0]
                    tif_file = os.path.join(tmpdir, tif_file[0])
                    return tif_file
        return file_path

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
                self.created or not self.input_layer.is_available()
        ):
            print(f"Processing {self.file['Key']}")
            media_root = self.storage.location or settings.MEDIA_ROOT
            if isinstance(self.storage, FileSystemStorage):
                download_path = os.path.join(media_root, self.file['Key'])
                os.makedirs(os.path.dirname(download_path), exist_ok=True)
                if self.source == InputLayer.LayerSources.NATURE_BASE:
                    download_path = self.handle_nature_base(download_path)
                    if not download_path:
                        self.input_layer.delete()
                        return
                iteration = 0
                while iteration < 3:
                    try:
                        self.read_metadata(download_path)
                    except RasterioIOError:
                        iteration += 1
                        if iteration == 3 and (
                            self.input_layer.name == '' or
                            self.input_layer.file is None
                        ):
                            self.input_layer.delete()
                    else:
                        try:
                            os.remove(download_path)
                        except OSError:
                            pass
                        break
            else:
                iteration = 0
                while iteration < 3:
                    with tempfile.NamedTemporaryFile() as tmpfile:
                        tif_file = tmpfile.name
                        if self.source == InputLayer.LayerSources.CPLUS:
                            boto3_client = self.storage.connection.meta.client
                            boto3_client.download_file(
                                self.storage.bucket_name,
                                self.file['Key'],
                                tmpfile.name,
                                Config=settings.AWS_TRANSFER_CONFIG
                            )
                        elif self.source == InputLayer.LayerSources.NATURE_BASE:  # noqa
                            tif_file = self.handle_nature_base(tmpfile.name)
                        if not tif_file:
                            self.input_layer.delete()
                            return
                        try:
                            self.read_metadata(tif_file)
                        except RasterioIOError:
                            iteration += 1
                            if iteration == 3 and (
                                self.input_layer.name == '' or
                                self.input_layer.file is None
                            ):
                                self.input_layer.delete()
                        else:
                            break


def delete_invalid_default_layers():
    """Delete invalid default layers in DB

    :return: None
    :rtype: None
    """
    common_layers = InputLayer.objects.filter(
        privacy_type=InputLayer.PrivacyTypes.COMMON
    )
    invalid_common_layers = common_layers.filter(
        Q(name='') | Q(file='')
    )
    invalid_common_layers.delete()


def sync_nature_base():
    """
    Sync NatureBase NCS Pathways
    """
    print("Syncing NatureBase NCS Pathways")
    storage = select_input_layer_storage()
    component_type = InputLayer.ComponentTypes.NCS_PATHWAY
    admin_username = os.getenv('ADMIN_USERNAME')
    owner = User.objects.get(username=admin_username)
    url = (
        "https://content.ncsmap.org/items/spatial_metadata?limit=-1&sort="
        "title&filter[status][_in]=published&fields=id,title,short_summary,"
        "download_links,cog_url,date_updated,action"
    )
    response = requests.get(url)

    if response.status_code == 200:
        results = response.json()['data']
        for result in results:
            if result['title'] != 'All NCS Pathway Data':
                last_modified = datetime.fromisoformat(
                    result['date_updated']
                )
                url = result['cog_url'] or result['download_links'][0]['url']
                action = -1
                if result.get('action') == "protect":
                    action = 0
                elif result.get('action') == "restore":
                    action = 1
                elif result.get('action') == "manage":
                    action = 2

                file = {
                    "Key": (
                        f"common_layers/ncs_pathway/"
                        f"{InputLayer.LayerSources.NATURE_BASE}/"
                        f"{os.path.basename(url)}"
                    ),
                    "LastModified": last_modified,
                    "url": url
                }
                file.update(result)
                file["action"] = action
                ProcessFile(
                    storage,
                    owner,
                    component_type,
                    file,
                    source=InputLayer.LayerSources.NATURE_BASE
                ).run()


def sync_cplus_layers():
    print("Syncing CPLUS NCS Pathways")
    storage = select_input_layer_storage()
    component_types = [c[0] for c in InputLayer.ComponentTypes.choices]
    admin_username = os.getenv('ADMIN_USERNAME')
    owner = User.objects.get(username=admin_username)

    non_cplus_layer_keys = InputLayer.objects.exclude(
        source=InputLayer.LayerSources.CPLUS
    ).values_list('file', flat=True)
    if isinstance(storage, FileSystemStorage):
        media_root = storage.location or settings.MEDIA_ROOT
        results = list(
            Path(
                os.path.join(media_root, COMMON_LAYERS_DIR)
            ).rglob("*.tif")
        )

        for layer in results:
            layer = str(layer)
            key = layer.replace(media_root + '/', '')
            component_type = key.split('/')[1]
            if key in non_cplus_layer_keys:
                continue
            download_path = os.path.join(media_root, key)
            last_modified = datetime.fromtimestamp(
                os.path.getmtime(download_path),
                tz=timezone.now().tzinfo
            )
            file = {
                "Key": key,
                "LastModified": last_modified
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
                if file['Key'] in non_cplus_layer_keys:
                    continue
                ProcessFile(storage, owner, component_type, file).run()
