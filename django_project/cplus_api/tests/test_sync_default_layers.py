import os
from shutil import copyfile

from core.settings.utils import absolute_path
from cplus_api.models.layer import (
    InputLayer,
    COMMON_LAYERS_DIR
)
from cplus_api.tasks.sync_default_layers import sync_default_layers
from cplus_api.tests.common import BaseAPIViewTransactionTest


class TestSyncDefaultLayer(BaseAPIViewTransactionTest):
    def setUp(self, *args, **kwargs):
        super().setUp(*args, **kwargs)
        # print(help(self))
        # breakpoint()
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
