from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from cplus_api.tests.factories import (
    InputLayerF,
    OutputLayerF,
    UserF
)
from cplus_api.models.layer import (
    InputLayer,
    OutputLayer
)
from cplus_api.models.profile import UserRoleType
from cplus_api.tasks.remove_layers import remove_layers


class TestRemoveLayers(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.int_user = UserF.create()
        cls.int_user.user_profile.role = UserRoleType.objects.get(
            name="Internal"
        )
        cls.int_user.user_profile.save()
        cls.ext_user = UserF.create()
        cls.ext_user.user_profile.role = UserRoleType.objects.get(
            name="External"
        )

    def test_layers_more_than_2_weeks_removed(self):
        input_layer = InputLayerF.create(
            created_on=timezone.now() - timedelta(days=15),
            owner=self.ext_user
        )
        output_layer = OutputLayerF.create(
            created_on=timezone.now() - timedelta(days=15),
            owner=self.ext_user
        )
        remove_layers()
        self.assertFalse(
            InputLayer.objects.filter(uuid=input_layer.uuid).exists()
        )
        self.assertFalse(
            OutputLayer.objects.filter(uuid=output_layer.uuid).exists()
        )

    def test_layers_less_than_2_weeks_not_removed(self):
        input_layer = InputLayerF.create(
            created_on=timezone.now() - timedelta(days=10),
            owner=self.ext_user
        )
        output_layer = OutputLayerF.create(
            created_on=timezone.now() - timedelta(days=10),
            owner=self.ext_user
        )
        remove_layers()
        self.assertTrue(
            InputLayer.objects.filter(uuid=input_layer.uuid).exists()
        )
        self.assertTrue(OutputLayer.objects.filter(
            uuid=output_layer.uuid).exists()
                        )

    def test_internal_user_layer_not_removed(self):
        input_layer = InputLayerF.create(
            created_on=timezone.now() - timedelta(days=15),
            owner=self.int_user
        )
        output_layer = OutputLayerF.create(
            created_on=timezone.now() - timedelta(days=15),
            owner=self.int_user
        )
        remove_layers()
        self.assertTrue(
            InputLayer.objects.filter(uuid=input_layer.uuid).exists()
        )
        self.assertTrue(
            OutputLayer.objects.filter(uuid=output_layer.uuid).exists()
        )
