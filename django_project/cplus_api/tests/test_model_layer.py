from django.test import TestCase
from cplus_api.tests.factories import InputLayerF, OutputLayerF
from cplus_api.models.layer import (
    input_layer_dir_path,
    output_layer_dir_path,
    InputLayer
)


class TestModelLayer(TestCase):

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
