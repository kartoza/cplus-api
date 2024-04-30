from datetime import timedelta
from django.utils import timezone
from cplus_api.tests.factories import (
    InputLayerF,
    OutputLayerF
)
from cplus_api.models.layer import (
    InputLayer,
    OutputLayer
)
from cplus_api.tasks.remove_layers import remove_layers
from cplus_api.tests.common import BaseAPIViewTransactionTest


class TestRemoveLayers(BaseAPIViewTransactionTest):
    """
    Test the remove_layers functions that is used by automatic layer
    removal.
    """

    def test_private_input_layers_more_than_2_weeks_removed(self):
        """
        Test that private input layers that were created more than 2 weeks ago
        will be automatically removed
        """
        input_layer = InputLayerF.create(
            created_on=timezone.now() - timedelta(days=15),
            privacy_type=InputLayer.PrivacyTypes.PRIVATE
        )
        remove_layers()
        self.assertFalse(
            InputLayer.objects.filter(uuid=input_layer.uuid).exists()
        )

    def test_input_layers_not_removed(self):
        """
        Test non private input layers or layers that were created
        less than 2 weeks ago will not be automatically removed
        """
        input_layer_1 = InputLayerF.create(
            created_on=timezone.now() - timedelta(days=10),
            privacy_type=InputLayer.PrivacyTypes.PRIVATE
        )
        input_layer_2 = InputLayerF.create(
            created_on=timezone.now() - timedelta(days=15),
            privacy_type=InputLayer.PrivacyTypes.COMMON
        )
        remove_layers()
        self.assertTrue(
            InputLayer.objects.filter(uuid=input_layer_1.uuid).exists()
        )
        self.assertTrue(
            InputLayer.objects.filter(uuid=input_layer_2.uuid).exists()
        )

    def test_output_layers_removed(self):
        """
        Test that output layer other than final or having group not
        specified in SitePreferences.output_group_to_keep,
        will be removed automatically.
        """
        output_layer_1 = OutputLayerF.create(
            created_on=timezone.now() - timedelta(days=15),
            is_final_output=False
        )
        output_layer_2 = OutputLayerF.create(
            created_on=timezone.now() - timedelta(days=15),
            is_final_output=False,
            group='some_group'
        )
        remove_layers()
        self.assertFalse(
            OutputLayer.objects.filter(uuid=output_layer_1.uuid).exists()
        )
        self.assertFalse(OutputLayer.objects.filter(
            uuid=output_layer_2.uuid).exists()
        )

    def test_output_layers_not_removed(self):
        """
        Test that final output layer or having group specified in
        SitePreferences.output_group_to_keep, will not be removed
        automatically.
        """
        output_layer_1 = OutputLayerF.create(
            created_on=timezone.now() - timedelta(days=15),
            is_final_output=True
        )
        output_layer_2 = OutputLayerF.create(
            created_on=timezone.now() - timedelta(days=15),
            is_final_output=False,
            group='weighted_ims'
        )
        remove_layers()
        self.assertTrue(
            OutputLayer.objects.filter(uuid=output_layer_1.uuid).exists()
        )
        self.assertTrue(OutputLayer.objects.filter(
            uuid=output_layer_2.uuid).exists()
        )
