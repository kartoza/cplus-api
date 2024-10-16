import os
import tempfile
import time
from datetime import timedelta
from shutil import copyfile
from unittest.mock import patch, MagicMock

from django.utils import timezone
from rasterio.errors import RasterioIOError
from storages.backends.s3 import S3Storage

from core.settings.utils import absolute_path
from cplus_api.models.layer import (
    InputLayer,
    COMMON_LAYERS_DIR
)
from cplus_api.tasks.sync_default_layers import sync_default_layers
from cplus_api.tests.common import BaseAPIViewTransactionTest
from cplus_api.tests.factories import InputLayerF
from cplus_api.utils.layers import ProcessFile


class TestSyncDefaultLayer(BaseAPIViewTransactionTest):
    def setUp(self, *args, **kwargs):
        super().setUp(*args, **kwargs)
        self.superuser.username = os.getenv('ADMIN_USERNAME')
        self.superuser.save()

    def base_run(self):
        # Check Input Layer before test
        input_layers = InputLayer.objects.filter(
            name='test_pathway_2.tif',
            owner=self.superuser,
            privacy_type=InputLayer.PrivacyTypes.COMMON,
            component_type=InputLayer.ComponentTypes.NCS_PATHWAY
        )
        self.assertFalse(input_layers.exists())

        source_path = absolute_path(
            'cplus_api', 'tests', 'data',
            'pathways', 'test_pathway_2.tif'
        )
        dest_path = (
            f'/home/web/media/minio_test/{COMMON_LAYERS_DIR}/'
            f'{InputLayer.ComponentTypes.NCS_PATHWAY}/test_pathway_2.tif'
        )
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        copyfile(source_path, dest_path)
        sync_default_layers()
        input_layers = input_layers.all()
        input_layer = input_layers[0]
        first_modified_on = input_layer.modified_on
        self.assertTrue(input_layers.exists())
        metadata = {
            'crs': 'EPSG:32735',
            'nodata_value': -9999.0,
            'is_raster': True,
            'resolution': [19.676449999999022, 19.676448888890445],
            'is_geographic': False,
            'unit': 'm'
        }
        self.assertEqual(input_layer.name, 'test_pathway_2.tif')
        self.assertEqual(input_layer.description, 'test_pathway_2.tif')
        self.assertEqual(input_layer.metadata, metadata)
        self.assertEqual(input_layer.size, os.path.getsize(source_path))

        # Rerun sync default layers
        sync_default_layers()
        # Check modified time is not changing, because the file is not updated
        input_layer.refresh_from_db()
        self.assertEqual(input_layer.modified_on, first_modified_on)
        return input_layer, source_path, dest_path

    def test_new_layer(self):
        """
        Test when a new file is added to the common layers directory
        :return:
        :rtype:
        """
        self.base_run()

    def test_file_updated(self):
        input_layer, source_path, dest_path = self.base_run()
        time.sleep(5)
        first_modified_on = input_layer.modified_on
        copyfile(source_path, dest_path)
        sync_default_layers()

        # Check modified_on is updated
        input_layer.refresh_from_db()
        self.assertNotEquals(input_layer.modified_on, first_modified_on)

        input_layer.name = 'New Name'
        input_layer.description = 'New Description'
        input_layer.save()
        input_layer.refresh_from_db()
        self.assertEqual(input_layer.name, 'New Name')
        self.assertEqual(input_layer.description, 'New Description')

    def test_delete_invalid_layers(self):
        input_layer, source_path, dest_path = self.base_run()
        invalid_common_layer_1 = InputLayerF.create(
            name='',
            privacy_type=InputLayer.PrivacyTypes.COMMON,
            file=input_layer.file
        )
        invalid_common_layer_2 = InputLayerF.create(
            name='invalid_common_layer_2',
            privacy_type=InputLayer.PrivacyTypes.COMMON,
            file=None
        )
        private_layer_1 = InputLayerF.create(
            name='',
            privacy_type=InputLayer.PrivacyTypes.PRIVATE,
            file=input_layer.file
        )
        private_layer_2 = InputLayerF.create(
            name='private_layer_2',
            privacy_type=InputLayer.PrivacyTypes.PRIVATE
        )

        sync_default_layers()

        # Calling refresh_from_db() on these 2 variable would result
        # in InputLayer.DoesNotExist as they have been deleted,
        # because they are invalid common layers
        with self.assertRaises(InputLayer.DoesNotExist):
            invalid_common_layer_1.refresh_from_db()
        with self.assertRaises(InputLayer.DoesNotExist):
            invalid_common_layer_2.refresh_from_db()

        # These layers are not deleted, so we could still call refresh_from_db
        private_layer_1.refresh_from_db()
        private_layer_2.refresh_from_db()

    def test_invalid_input_layers_not_created(self):
        source_path = absolute_path(
            'cplus_api', 'tests', 'data',
            'pathways', 'test_pathway_2.tif'
        )
        dest_path = (
            f'/home/web/media/minio_test/{COMMON_LAYERS_DIR}/'
            f'{InputLayer.ComponentTypes.NCS_PATHWAY}/test_pathway_2.tif'
        )
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        copyfile(source_path, dest_path)
        with patch.object(
                ProcessFile, 'read_metadata', autospec=True
        ) as mock_read_metadata:
            mock_read_metadata.side_effect = [
                RasterioIOError('error'),
                RasterioIOError('error'),
                RasterioIOError('error')
            ]
            sync_default_layers()

            self.assertFalse(InputLayer.objects.exists())

    def test_invalid_input_layers_not_deleted(self):
        input_layer, source_path, dest_path = self.base_run()
        time.sleep(5)
        first_modified_on = input_layer.modified_on
        copyfile(source_path, dest_path)
        sync_default_layers()
        with patch.object(
                ProcessFile, 'read_metadata', autospec=True
        ) as mock_read_metadata:
            mock_read_metadata.side_effect = [
                RasterioIOError('error'),
                RasterioIOError('error'),
                RasterioIOError('error')
            ]
            sync_default_layers()

            self.assertTrue(InputLayer.objects.exists())

            # Check modified_on is updated
            input_layer.refresh_from_db()
            self.assertNotEquals(input_layer.modified_on, first_modified_on)

    def run_s3(self, mock_storage, mock_named_tmp_file=None):
        source_path = absolute_path(
            'cplus_api', 'tests', 'data',
            'pathways', 'test_pathway_2.tif'
        )
        dest_path = (
            f'/home/web/media/minio_test/{COMMON_LAYERS_DIR}/'
            f'{InputLayer.ComponentTypes.NCS_PATHWAY}/test_pathway_2.tif'
        )
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        copyfile(source_path, dest_path)

        storage = S3Storage(bucket_name='test-bucket')
        s3_client = MagicMock()
        s3_client.list_objects.return_value = {
            'Contents': [
                {
                    'Key': 'common_layers/ncs_pathway/test_pathway_2.tif',
                    'LastModified': timezone.now() + timedelta(days=1)
                }
            ]
        }
        storage.connection.meta.client = s3_client
        mock_storage.return_value = storage
        if mock_named_tmp_file:
            (mock_named_tmp_file.return_value.
             __enter__.return_value).name = dest_path
        sync_default_layers()

    @patch('cplus_api.utils.layers.select_input_layer_storage')
    def test_invalid_input_layers_not_created_s3(self, mock_storage):
        self.run_s3(mock_storage)
        self.assertFalse(InputLayer.objects.exists())

    @patch('cplus_api.utils.layers.select_input_layer_storage')
    @patch.object(tempfile, 'NamedTemporaryFile')
    def test_invalid_input_layers_created_s3(
            self,
            mock_named_tmp_file,
            mock_storage
    ):
        self.run_s3(mock_storage, mock_named_tmp_file)
        self.assertTrue(InputLayer.objects.exists())
