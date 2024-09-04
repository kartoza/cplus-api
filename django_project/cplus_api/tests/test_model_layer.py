import os
import tempfile
import mock
from django.test import Client
from rest_framework import status
from django.urls import reverse
from django.contrib.auth.models import User
from core.settings.utils import absolute_path
from cplus_api.tests.factories import InputLayerF, OutputLayerF
from cplus_api.models.layer import (
    input_layer_dir_path,
    output_layer_dir_path,
    InputLayer
)
from cplus_api.tasks.verify_input_layer import verify_input_layer
from cplus_api.tests.common import BaseAPIViewTransactionTest, mocked_process


class TestModelLayer(BaseAPIViewTransactionTest):

    def test_input_layer_dir_path(self):
        # private layer
        input_layer = InputLayerF.create()
        self.assertFalse(input_layer.is_available())
        path = input_layer_dir_path(input_layer, 'test.tif')
        self.assertEqual(
            path,
            f'{str(input_layer.owner.pk)}/{input_layer.component_type}/'
            'test.tif'
        )
        # common layer
        input_layer = InputLayerF.create(
            privacy_type=InputLayer.PrivacyTypes.COMMON)
        path = input_layer_dir_path(input_layer, 'test.tif')
        self.assertEqual(
            path,
            f'common_layers/{input_layer.component_type}/'
            'test.tif'
        )
        # internal layer
        input_layer = InputLayerF.create(
            privacy_type=InputLayer.PrivacyTypes.INTERNAL)
        path = input_layer_dir_path(input_layer, 'test.tif')
        self.assertEqual(
            path,
            f'internal_layers/{input_layer.component_type}/'
            'test.tif'
        )
        self.assertEqual(str(input_layer), f"{input_layer.name} - ncs_pathway")

    def test_output_layer_dir_path(self):
        # intermediate output layer
        output_layer = OutputLayerF.create(group='abcd')
        path = output_layer_dir_path(output_layer, 'test.tif')
        self.assertEqual(
            path,
            f'{str(output_layer.owner.pk)}/{str(output_layer.scenario.uuid)}/'
            'abcd/test.tif'
        )
        # final output layer
        output_layer = OutputLayerF.create(is_final_output=True)
        path = output_layer_dir_path(output_layer, 'test.tif')
        self.assertEqual(
            path,
            f'{str(output_layer.owner.pk)}/{str(output_layer.scenario.uuid)}/'
            'test.tif'
        )

        self.assertEqual(
            str(output_layer),
            f"{output_layer.name} - Final - {output_layer.uuid}"
        )

    def test_download_to_working_directory(self):
        owner = User.objects.first()

        # Test tif
        input_layer = InputLayerF.create(owner=owner)
        file_path = absolute_path(
            'cplus_api', 'tests', 'data',
            'models', 'test_model_1.tif'
        )
        self.store_layer_file(input_layer, file_path)
        tmp_dir = tempfile.mkdtemp()
        file_path = input_layer.download_to_working_directory(tmp_dir)
        self.assertTrue(file_path.startswith(
            os.path.join(tmp_dir, input_layer.get_component_type_display())
        ))
        self.assertTrue(os.path.exists(file_path))

        # test zip
        input_layer_2 = InputLayerF.create(
            owner=owner,
            layer_type=InputLayer.LayerTypes.VECTOR,
            component_type=InputLayer.ComponentTypes.MASK_LAYER
        )
        file_path = absolute_path(
            'cplus_api', 'tests', 'data',
            'mask_layers', 'shapefile.zip'
        )
        self.store_layer_file(input_layer_2, file_path)
        tmp_dir = tempfile.mkdtemp()
        file_path = input_layer_2.download_to_working_directory(tmp_dir)
        self.assertTrue(os.path.exists(file_path))
        self.assertTrue(file_path.startswith(
            os.path.join(
                tmp_dir,
                input_layer_2.get_component_type_display(),
                os.path.basename(
                    input_layer_2.file.name.replace('.zip', '_zip')
                ),
                'shops_poly'
            )
        ))

        # Test invalid
        input_layer_3 = InputLayerF.create(
            owner=owner,
            layer_type=InputLayer.LayerTypes.VECTOR,
            component_type=InputLayer.ComponentTypes.MASK_LAYER
        )
        file_path = absolute_path(
            'cplus_api', 'tests', 'data',
            'mask_layers', 'shapefile_invalid.zip'
        )
        self.store_layer_file(input_layer_3, file_path)
        tmp_dir = tempfile.mkdtemp()
        file_path = input_layer_3.download_to_working_directory(tmp_dir)
        self.assertIsNone(file_path)

        # Test file not available
        input_layer_4 = InputLayerF.create(
            owner=owner,
            layer_type=InputLayer.LayerTypes.VECTOR,
            component_type=InputLayer.ComponentTypes.MASK_LAYER
        )
        file_path = absolute_path(
            'cplus_api', 'tests', 'data',
            'models', 'test_model_1.tif'
        )
        tmp_dir = tempfile.mkdtemp()
        file_path = input_layer_4.download_to_working_directory(tmp_dir)
        self.assertIsNone(file_path)

    def test_is_in_correct_directory(self):
        input_layer = InputLayerF.create()
        file_path = absolute_path(
            'cplus_api', 'tests', 'data',
            'models', 'test_model_1.tif'
        )
        self.store_layer_file(input_layer, file_path)
        self.assertTrue(input_layer.is_in_correct_directory())
        input_layer.privacy_type = InputLayer.PrivacyTypes.COMMON
        input_layer.save()
        self.assertFalse(input_layer.is_in_correct_directory())
        input_layer.privacy_type = InputLayer.PrivacyTypes.INTERNAL
        input_layer.save()
        self.assertFalse(input_layer.is_in_correct_directory())

    def test_fix_layer_metadata(self):
        input_layer = InputLayerF.create(
            name='test_model_fix_1.tif'
        )
        input_layer.fix_layer_metadata()
        self.assertFalse(input_layer.is_available())
        self.assertEqual(input_layer.size, 0)
        file_path = absolute_path(
            'cplus_api', 'tests', 'data',
            'models', 'test_model_1.tif'
        )
        file_size = os.stat(file_path).st_size
        self.store_layer_file(input_layer, file_path, input_layer.name)
        input_layer.refresh_from_db()
        self.assertTrue(input_layer.is_available())
        input_layer.fix_layer_metadata()
        self.assertEqual(input_layer.size, file_size)
        input_layer.privacy_type = InputLayer.PrivacyTypes.COMMON
        input_layer.save()
        self.assertFalse(input_layer.is_in_correct_directory())
        input_layer.fix_layer_metadata()
        input_layer.refresh_from_db()
        self.assertTrue(input_layer.is_in_correct_directory())

    def test_verify_input_layer(self):
        input_layer = InputLayerF.create(
            name='test_model_verify_1.tif',
            privacy_type=InputLayer.PrivacyTypes.COMMON
        )
        file_path = absolute_path(
            'cplus_api', 'tests', 'data',
            'models', 'test_model_1.tif'
        )
        file_size = os.stat(file_path).st_size
        self.store_layer_file(input_layer, file_path, input_layer.name)
        input_layer.refresh_from_db()
        self.assertTrue(input_layer.is_available())
        input_layer.privacy_type = InputLayer.PrivacyTypes.PRIVATE
        input_layer.save()
        verify_input_layer(input_layer.id)
        input_layer.refresh_from_db()
        self.assertTrue(input_layer.is_in_correct_directory())
        self.assertEqual(input_layer.size, file_size)

    @mock.patch('cplus_api.admin.verify_input_layer.delay')
    def test_trigger_verify_input_layer(self, mocked_process_param):
        mocked_process_param.side_effect = mocked_process
        input_layer = InputLayerF.create(
            name='test_model_verify_1.tif',
            privacy_type=InputLayer.PrivacyTypes.COMMON
        )
        file_path = absolute_path(
            'cplus_api', 'tests', 'data',
            'models', 'test_model_1.tif'
        )
        self.store_layer_file(input_layer, file_path, input_layer.name)
        client = Client()
        client.force_login(self.superuser)
        response = client.post(
            reverse('admin:cplus_api_inputlayer_changelist'),
            {
                'action': 'trigger_verify_input_layer',
                '_selected_action': [input_layer.id]
            },
            follow=True
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mocked_process_param.assert_called_once()
