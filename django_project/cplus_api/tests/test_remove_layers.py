import mock
import os
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from cplus_api.tests.factories import (
    InputLayerF,
    OutputLayerF,
    MultipartUploadF
)
from cplus_api.models.layer import (
    InputLayer,
    OutputLayer,
    MultipartUpload,
    TemporaryLayer
)
from cplus_api.tasks.remove_layers import (
    remove_layers,
    clean_multipart_upload
)
from cplus_api.tests.common import BaseAPIViewTransactionTest, MockS3Client


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

    def test_temporary_layers_removed(self):
        """Test to remove temporary layers."""
        file_path = os.path.join(
            settings.TEMPORARY_LAYER_DIR,
            'test.txt'
        )
        with open(file_path, 'w') as f:
            f.write('echo')
        self.assertTrue(os.path.exists(file_path))
        temp_layer = TemporaryLayer.objects.create(
            file_name='test.txt',
            size=1
        )
        temp_layer.created_on = timezone.now() - timedelta(days=15)
        temp_layer.save()
        remove_layers()
        self.assertFalse(
            TemporaryLayer.objects.filter(
                id=temp_layer.id
            ).exists()
        )
        self.assertFalse(os.path.exists(file_path))

    @mock.patch('boto3.client')
    def test_clean_multipart_upload(self, mocked_s3):
        input_layer = InputLayerF.create(
            privacy_type=InputLayer.PrivacyTypes.PRIVATE
        )
        s3_client = MockS3Client()
        mocked_s3.return_value = s3_client
        # record with less than 7days and is_aborted=False
        # record with less than 1day and is_aborted=True
        u1 = MultipartUploadF.create(
            created_on=timezone.now() - timedelta(days=5),
            is_aborted=False
        )
        u2 = MultipartUploadF.create(
            created_on=timezone.now() - timedelta(minutes=5),
            is_aborted=True
        )
        clean_multipart_upload()
        # both should exist and not modified
        self.assertEqual(
            MultipartUpload.objects.filter(
                upload_id__in=[u1.upload_id, u2.upload_id]
            ).count(),
            2
        )
        MultipartUpload.objects.all().delete()

        # record with more than 7days and is_aborted=False
        # record with more than 1day and is_aborted=True
        u1 = MultipartUploadF.create(
            created_on=timezone.now() - timedelta(days=10),
            is_aborted=False
        )
        u2 = MultipartUploadF.create(
            created_on=timezone.now() - timedelta(days=2),
            is_aborted=True,
        )
        clean_multipart_upload()
        # but without input_layer, both should be removed
        self.assertEqual(MultipartUpload.objects.count(), 0)

        # record with more than 7days and is_aborted=False
        # record with more than 1day and is_aborted=True
        u1 = MultipartUploadF.create(
            created_on=timezone.now() - timedelta(days=10),
            is_aborted=False,
            input_layer_uuid=input_layer.uuid
        )
        u2 = MultipartUploadF.create(
            created_on=timezone.now() - timedelta(days=2),
            is_aborted=True,
            input_layer_uuid=input_layer.uuid
        )
        clean_multipart_upload()
        # parts return >0, both should be is_aborted=True
        self.assertEqual(
            MultipartUpload.objects.filter(is_aborted=True).count(), 2)
        MultipartUpload.objects.all().delete()

        # record with more than 7days and is_aborted=False
        # record with more than 1day and is_aborted=True
        u1 = MultipartUploadF.create(
            created_on=timezone.now() - timedelta(days=10),
            is_aborted=False,
            input_layer_uuid=input_layer.uuid
        )
        u2 = MultipartUploadF.create(
            created_on=timezone.now() - timedelta(days=2),
            is_aborted=True,
            input_layer_uuid=input_layer.uuid
        )
        s3_client.mock_parts = {
            'Parts': []
        }
        clean_multipart_upload()
        # parts return 0, both should be removed
        self.assertEqual(MultipartUpload.objects.count(), 0)
        self.assertFalse(
            InputLayer.objects.filter(
                uuid=input_layer.uuid
            ).exists()
        )
