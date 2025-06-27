import os
import uuid
import mock
from django.contrib.gis.geos import Polygon
from django.test import override_settings
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from core.settings.utils import absolute_path
from cplus_api.models.layer import (
    InputLayer,
    input_layer_dir_path,
    select_input_layer_storage,
    MultipartUpload
)
from cplus_api.api_views.layer import (
    LayerList,
    LayerDetail,
    LayerUpload,
    LayerUploadStart,
    LayerUploadFinish,
    CheckLayer,
    is_internal_user,
    validate_layer_access,
    LayerUploadAbort,
    FetchLayerByClientId,
    DefaultLayerList,
    ReferenceLayerDownload,
    DefaultLayerDownload
)
from cplus_api.models.profile import UserProfile
from cplus_api.utils.api_helper import convert_size
from cplus_api.tests.common import (
    FakeResolverMatchV1,
    BaseAPIViewTransactionTest,
    MockS3Client
)
from cplus_api.tests.factories import InputLayerF, UserF


class TestLayerAPIView(BaseAPIViewTransactionTest):

    def test_is_internal_user(self):
        user_1 = UserF.create()
        # has external role
        self.assertFalse(is_internal_user(user_1))
        # no role
        user_profile = user_1.user_profile
        user_profile.role = None
        user_profile.save()
        self.assertFalse(is_internal_user(user_1))
        # no user_profile
        user_profile.delete()
        self.assertFalse(UserProfile.objects.filter(user=user_1).exists())
        user_1.refresh_from_db()
        self.assertFalse(is_internal_user(user_1))
        # has internal role
        user_2 = self.create_internal_user()
        self.assertTrue(is_internal_user(user_2))

    def test_layer_list(self):
        request = self.factory.get(
            reverse('v1:layer-list')
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.superuser
        view = LayerList.as_view()
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'], [])
        input_layer = InputLayerF.create(
            privacy_type=InputLayer.PrivacyTypes.COMMON
        )
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)
        find_layer = self.find_layer_from_response(
            response.data['results'], input_layer.uuid)
        self.assertTrue(find_layer)
        self.assertFalse(find_layer['url'])
        self.assertFalse(input_layer.file)
        # non existing file in storage
        input_layer.file.name = (
            'common_layers/ncs_pathway/test_model_2_123.tif'
        )
        input_layer.save()
        self.assertTrue(input_layer.file)
        self.assertFalse(input_layer.is_available())
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)
        find_layer = self.find_layer_from_response(
            response.data['results'], input_layer.uuid)
        self.assertTrue(find_layer)
        self.assertFalse(find_layer['url'])
        file_path = absolute_path(
            'cplus_api', 'tests', 'data',
            'models', 'test_model_1.tif'
        )
        self.store_layer_file(input_layer, file_path)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)
        find_layer = self.find_layer_from_response(
            response.data['results'], input_layer.uuid)
        self.assertTrue(find_layer)
        self.assertTrue(find_layer['url'])

    def test_default_layer_list(self):
        request = self.factory.get(
            reverse('v1:layer-default-list')
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.superuser
        view = DefaultLayerList.as_view()
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
        input_layer = InputLayerF.create(
            privacy_type=InputLayer.PrivacyTypes.COMMON
        )
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        find_layer = self.find_layer_from_response(
            response.data, input_layer.uuid)
        self.assertTrue(find_layer)
        self.assertFalse(find_layer['url'])
        self.assertFalse(input_layer.file)

    def test_layer_access(self):
        input_layer_1 = InputLayerF.create(
            privacy_type=InputLayer.PrivacyTypes.COMMON
        )
        input_layer_2 = InputLayerF.create(
            privacy_type=InputLayer.PrivacyTypes.INTERNAL
        )
        input_layer_3 = InputLayerF.create(
            privacy_type=InputLayer.PrivacyTypes.PRIVATE
        )
        self.assertTrue(validate_layer_access(
            input_layer_1, self.superuser
        ))
        self.assertTrue(validate_layer_access(
            input_layer_1, self.user_1
        ))
        user_2 = self.create_internal_user()
        self.assertTrue(validate_layer_access(
            input_layer_2, user_2
        ))
        self.assertFalse(validate_layer_access(
            input_layer_3, self.user_1
        ))
        self.assertTrue(validate_layer_access(
            input_layer_3, input_layer_3.owner
        ))
        # upload access
        layer_upload_view = LayerUpload()
        self.assertTrue(layer_upload_view.validate_upload_access(
            InputLayer.PrivacyTypes.COMMON, self.superuser
        ))
        self.assertTrue(layer_upload_view.validate_upload_access(
            InputLayer.PrivacyTypes.INTERNAL, user_2
        ))
        with self.assertRaises(PermissionDenied):
            layer_upload_view.validate_upload_access(
                InputLayer.PrivacyTypes.COMMON, self.user_1
            )
        self.assertTrue(layer_upload_view.validate_upload_access(
            InputLayer.PrivacyTypes.PRIVATE, self.user_1
        ))
        input_layer_4 = InputLayerF.create(
            privacy_type=InputLayer.PrivacyTypes.PRIVATE,
            owner=self.user_1
        )
        self.assertTrue(layer_upload_view.validate_upload_access(
            InputLayer.PrivacyTypes.PRIVATE, self.user_1,
            True, input_layer_4
        ))

    def test_layer_detail(self):
        view = LayerDetail.as_view()
        input_layer = InputLayerF.create(
            privacy_type=InputLayer.PrivacyTypes.PRIVATE
        )
        file_path = absolute_path(
            'cplus_api', 'tests', 'data',
            'models', 'test_model_1.tif'
        )
        self.store_layer_file(input_layer, file_path)
        kwargs = {
            'layer_uuid': str(input_layer.uuid)
        }
        request = self.factory.get(
            reverse('v1:layer-detail', kwargs=kwargs)
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.superuser
        response = view(request, **kwargs)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['url'])
        self.assertEqual(response.data['uuid'], str(input_layer.uuid))
        # forbidden
        request = self.factory.get(
            reverse('v1:layer-detail', kwargs=kwargs)
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.user_1
        response = view(request, **kwargs)
        self.assertEqual(response.status_code, 403)

    @override_settings(DEBUG=True)
    def test_layer_detail_from_dev(self):
        view = LayerDetail.as_view()
        input_layer = InputLayerF.create(
            privacy_type=InputLayer.PrivacyTypes.PRIVATE
        )
        file_path = absolute_path(
            'cplus_api', 'tests', 'data',
            'models', 'test_model_1.tif'
        )
        self.store_layer_file(input_layer, file_path)
        kwargs = {
            'layer_uuid': str(input_layer.uuid)
        }
        request = self.factory.get(
            reverse('v1:layer-detail', kwargs=kwargs)
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.superuser
        response = view(request, **kwargs)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['url'])
        self.assertEqual(response.data['uuid'], str(input_layer.uuid))

    def test_layer_delete(self):
        view = LayerDetail.as_view()
        input_layer = InputLayerF.create(
            privacy_type=InputLayer.PrivacyTypes.PRIVATE
        )
        file_path = absolute_path(
            'cplus_api', 'tests', 'data',
            'models', 'test_model_1.tif'
        )
        self.store_layer_file(input_layer, file_path)
        layer_uuid = input_layer.uuid
        kwargs = {
            'layer_uuid': str(layer_uuid)
        }
        # forbidden
        request = self.factory.delete(
            reverse('v1:layer-detail', kwargs=kwargs)
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.user_1
        response = view(request, **kwargs)
        self.assertEqual(response.status_code, 403)
        # successful
        request = self.factory.delete(
            reverse('v1:layer-detail', kwargs=kwargs)
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.superuser
        response = view(request, **kwargs)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            InputLayer.objects.filter(
                uuid=layer_uuid
            ).exists()
        )
        self.assertFalse(input_layer.is_available())

    def test_layer_update_partial(self):
        view = LayerDetail.as_view()
        input_layer = InputLayerF.create(
            privacy_type=InputLayer.PrivacyTypes.PRIVATE
        )
        file_path = absolute_path(
            'cplus_api', 'tests', 'data',
            'models', 'test_model_1.tif'
        )
        self.store_layer_file(input_layer, file_path)
        layer_uuid = input_layer.uuid
        kwargs = {
            'layer_uuid': str(layer_uuid)
        }
        # forbidden
        request = self.factory.patch(
            reverse('v1:layer-detail', kwargs=kwargs),
            data={'name': 'test_name'}
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.user_1
        response = view(request, **kwargs)
        self.assertEqual(response.status_code, 403)
        # successful
        request = self.factory.patch(
            reverse('v1:layer-detail', kwargs=kwargs),
            data={'name': 'test_name'}
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.superuser
        response = view(request, **kwargs)
        self.assertEqual(response.status_code, 200)
        input_layer.refresh_from_db()
        self.assertEqual(input_layer.name, 'test_name')

    def test_layer_upload(self):
        view = LayerUpload.as_view()
        file_path = absolute_path(
            'cplus_api', 'tests', 'data',
            'models', 'test_model_1.tif'
        )
        data = {
            'layer_type': 0,
            'component_type': 'ncs_carbon',
            'privacy_type': 'common',
            'client_id': 'client-test-123',
            'file': self.read_uploaded_file(file_path)
        }
        # invalid access
        request = self.factory.post(
            reverse('v1:layer-upload'), data
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.user_1
        response = view(request)
        self.assertEqual(response.status_code, 403)
        # upload successful
        data = {
            'layer_type': 0,
            'component_type': 'ncs_carbon',
            'privacy_type': 'common',
            'client_id': 'client-test-123',
            'file': self.read_uploaded_file(file_path)
        }
        request = self.factory.post(
            reverse('v1:layer-upload'), data
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.superuser
        response = view(request)
        self.assertEqual(response.status_code, 201)
        self.assertIn('uuid', response.data)
        layer_uuid = response.data['uuid']
        input_layer = InputLayer.objects.filter(
            uuid=layer_uuid
        ).first()
        self.assertTrue(input_layer)
        self.assertEqual(input_layer.layer_type, data['layer_type'])
        self.assertEqual(input_layer.component_type, data['component_type'])
        self.assertEqual(input_layer.privacy_type, data['privacy_type'])
        self.assertEqual(input_layer.client_id, data['client_id'])
        self.assertTrue(input_layer.size > 0)
        self.assertTrue(input_layer.is_available())
        # test update
        file_path = absolute_path(
            'cplus_api', 'tests', 'data',
            'pathways', 'test_pathway_1.tif'
        )
        data = {
            'layer_type': 0,
            'component_type': 'ncs_carbon',
            'privacy_type': 'private',
            'client_id': 'client-test-123',
            'file': self.read_uploaded_file(file_path),
            'uuid': layer_uuid
        }
        # test 403 update
        request = self.factory.post(
            reverse('v1:layer-upload'), data
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.user_1
        response = view(request)
        self.assertEqual(response.status_code, 403)
        # test successful update
        data = {
            'layer_type': 0,
            'component_type': 'ncs_carbon',
            'privacy_type': 'private',
            'client_id': 'client-test-123',
            'file': self.read_uploaded_file(file_path),
            'uuid': layer_uuid
        }
        request = self.factory.post(
            reverse('v1:layer-upload'), data
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.superuser
        response = view(request)
        self.assertEqual(response.status_code, 201)
        self.assertIn('uuid', response.data)
        input_layer.refresh_from_db()
        self.assertEqual(input_layer.privacy_type, data['privacy_type'])

    @override_settings(DEBUG=True)
    @mock.patch('boto3.client')
    def test_layer_upload_start(self, mocked_s3):
        s3_client = MockS3Client()
        mocked_s3.return_value = s3_client
        file_path = absolute_path(
            'cplus_api', 'tests', 'data',
            'models', 'test_model_1.tif'
        )
        base_filename = 'test_model_1_start.tif'
        view = LayerUploadStart.as_view()
        data = {
            'layer_type': 0,
            'component_type': 'ncs_carbon',
            'privacy_type': 'common',
            'client_id': 'client-test-123',
            'name': base_filename,
            'size': os.stat(file_path).st_size
        }
        request = self.factory.post(
            reverse('v1:layer-upload-start'), data
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.superuser
        response = view(request)
        self.assertEqual(response.status_code, 201)
        self.assertIn('uuid', response.data)
        self.assertIn('name', response.data)
        self.assertIn('upload_urls', response.data)
        self.assertEqual(response.data['name'], data['name'])
        input_layer = InputLayer.objects.filter(
            uuid=response.data['uuid']
        ).first()
        self.assertTrue(input_layer)
        self.assertFalse(input_layer.file)
        self.assertEqual(input_layer.size, data['size'])

        # test with existing file
        storage_backend = select_input_layer_storage()
        dest_file_path = os.path.join(
            storage_backend.location,
            input_layer_dir_path(input_layer, base_filename)
        )
        self.direct_upload_layer_file(file_path, dest_file_path)
        request = self.factory.post(
            reverse('v1:layer-upload-start'), data
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.superuser
        response = view(request)
        self.assertEqual(response.status_code, 201)
        self.assertNotEqual(response.data['name'], data['name'])
        input_layer = InputLayer.objects.filter(
            uuid=response.data['uuid']
        ).first()
        self.assertTrue(input_layer)
        self.assertFalse(input_layer.file)
        self.assertEqual(input_layer.size, data['size'])
        self.assertEqual(input_layer.name, response.data['name'])
        self.assertTrue(os.path.exists(dest_file_path))
        # test update should remove old file
        self.store_layer_file(
            input_layer, file_path, file_name=input_layer.name)
        input_layer.refresh_from_db()
        old_filename = input_layer.name
        old_file_path = os.path.join(
            storage_backend.location,
            input_layer_dir_path(input_layer, input_layer.name)
        )
        self.assertTrue(os.path.exists(old_file_path))
        self.assertTrue(storage_backend.exists(input_layer.file.name))
        data['uuid'] = str(input_layer.uuid)
        request = self.factory.post(
            reverse('v1:layer-upload-start'), data
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.superuser
        response = view(request)
        self.assertEqual(response.status_code, 201)
        input_layer.refresh_from_db()
        self.assertFalse(input_layer.file)
        self.assertEqual(input_layer.name, response.data['name'])
        self.assertFalse(storage_backend.exists(old_filename))
        self.assertFalse(os.path.exists(old_file_path))

    @mock.patch('boto3.client')
    def test_layer_upload_start_with_s3(self, mocked_s3):
        s3_client = MockS3Client()
        mocked_s3.return_value = s3_client
        file_path = absolute_path(
            'cplus_api', 'tests', 'data',
            'models', 'test_model_1.tif'
        )
        base_filename = 'test_model_1_start2.tif'
        view = LayerUploadStart.as_view()
        data = {
            'layer_type': 0,
            'component_type': 'ncs_carbon',
            'privacy_type': 'common',
            'client_id': 'client-test-123',
            'name': base_filename,
            'size': os.stat(file_path).st_size
        }
        request = self.factory.post(
            reverse('v1:layer-upload-start'), data
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.superuser
        response = view(request)
        self.assertEqual(response.status_code, 201)
        self.assertIn('uuid', response.data)
        self.assertIn('name', response.data)
        self.assertIn('upload_urls', response.data)
        self.assertEqual(response.data['name'], data['name'])
        self.assertEqual(
            response.data['upload_urls'],
            [{
                'part_number': 1,
                'url': 'this_is_url'
            }]
        )
        # test failed generate url
        s3_client.raise_exc = True
        data = {
            'layer_type': 0,
            'component_type': 'ncs_carbon',
            'privacy_type': 'common',
            'client_id': 'client-test-123',
            'name': base_filename,
            'size': os.stat(file_path).st_size
        }
        request = self.factory.post(
            reverse('v1:layer-upload-start'), data
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.superuser
        response = view(request)
        self.assertEqual(response.status_code, 400)

    @mock.patch('boto3.client')
    def test_layer_upload_start_with_s3_multipart(self, mocked_s3):
        s3_client = MockS3Client()
        mocked_s3.return_value = s3_client
        file_path = absolute_path(
            'cplus_api', 'tests', 'data',
            'models', 'test_model_1.tif'
        )
        base_filename = 'test_model_1_start2.tif'
        view = LayerUploadStart.as_view()
        data = {
            'layer_type': 0,
            'component_type': 'ncs_carbon',
            'privacy_type': 'common',
            'client_id': 'client-test-123',
            'name': base_filename,
            'size': os.stat(file_path).st_size,
            'number_of_parts': 2
        }
        request = self.factory.post(
            reverse('v1:layer-upload-start'), data
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.superuser
        response = view(request)
        self.assertEqual(response.status_code, 201)
        self.assertIn('uuid', response.data)
        self.assertIn('name', response.data)
        self.assertIn('upload_urls', response.data)
        self.assertEqual(response.data['name'], data['name'])
        self.assertEqual(
            response.data['upload_urls'],
            [{
                'part_number': 1,
                'url': 'this_is_url'
            }, {
                'part_number': 2,
                'url': 'this_is_url'
            }]
        )
        multipart_upload_id = response.data.get('multipart_upload_id', '')
        self.assertTrue(multipart_upload_id)
        self.assertTrue(MultipartUpload.objects.filter(
            upload_id=multipart_upload_id,
            input_layer_uuid=response.data['uuid']
        ).exists())

    def test_layer_upload_finish(self):
        view = LayerUploadFinish.as_view()
        file_path = absolute_path(
            'cplus_api', 'tests', 'data',
            'models', 'test_model_1.tif'
        )
        base_filename = 'test_model_1_finish.tif'
        input_layer = InputLayerF.create(
            privacy_type=InputLayer.PrivacyTypes.PRIVATE,
            name=base_filename,
            size=10
        )
        kwargs = {
            'layer_uuid': str(input_layer.uuid)
        }
        payload = {}
        # file not exist
        request = self.factory.post(
            reverse('v1:layer-upload-finish', kwargs=kwargs),
            data=payload, format='json'
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.superuser
        response = view(request, **kwargs)
        self.assertEqual(response.status_code, 400)
        self.check_validation_error_string(response.data, 'does not exist')
        input_layer.refresh_from_db()
        self.assertFalse(input_layer.file.name)
        # size not match
        storage_backend = select_input_layer_storage()
        dest_file_path = os.path.join(
            storage_backend.location,
            input_layer_dir_path(input_layer, base_filename)
        )
        self.direct_upload_layer_file(file_path, dest_file_path)
        request = self.factory.post(
            reverse('v1:layer-upload-finish', kwargs=kwargs),
            data=payload, format='json'
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.superuser
        response = view(request, **kwargs)
        self.assertEqual(response.status_code, 400)
        self.check_validation_error_string(
            response.data, 'file size missmatch')
        input_layer.refresh_from_db()
        self.assertFalse(input_layer.file.name)
        # succcess
        input_layer.size = os.stat(file_path).st_size
        input_layer.save(update_fields=['size'])
        request = self.factory.post(
            reverse('v1:layer-upload-finish', kwargs=kwargs),
            data=payload, format='json'
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.superuser
        response = view(request, **kwargs)
        self.assertEqual(response.status_code, 200)
        input_layer.refresh_from_db()
        self.assertTrue(input_layer.file.name)
        self.assertTrue(input_layer.is_available())

    @mock.patch('boto3.client')
    def test_layer_upload_finish_with_multipart(self, mocked_s3):
        s3_client = MockS3Client()
        mocked_s3.return_value = s3_client
        view = LayerUploadFinish.as_view()
        file_path = absolute_path(
            'cplus_api', 'tests', 'data',
            'models', 'test_model_1.tif'
        )
        base_filename = 'test_model_1_finish2.tif'
        input_layer = InputLayerF.create(
            privacy_type=InputLayer.PrivacyTypes.PRIVATE,
            name=base_filename,
            size=10
        )
        kwargs = {
            'layer_uuid': str(input_layer.uuid)
        }
        payload = {
            'multipart_upload_id': 'this_is_upload_id',
            'items': [{
                'part_number': 1,
                'etag': 'etag-1'
            }, {
                'part_number': 2,
                'etag': 'etag-2'
            }]
        }
        MultipartUpload.objects.create(
            upload_id=payload['multipart_upload_id'],
            input_layer_uuid=input_layer.uuid,
            created_on=timezone.now(),
            uploader=input_layer.owner,
            parts=10
        )
        input_layer.size = os.stat(file_path).st_size
        input_layer.save(update_fields=['size'])
        self.store_layer_file(input_layer, file_path, base_filename)
        request = self.factory.post(
            reverse('v1:layer-upload-finish', kwargs=kwargs),
            data=payload, format='json'
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.superuser
        response = view(request, **kwargs)
        self.assertEqual(response.status_code, 200)
        input_layer.refresh_from_db()
        self.assertTrue(input_layer.file.name)
        self.assertTrue(input_layer.is_available())
        self.assertFalse(MultipartUpload.objects.filter(
            upload_id=payload['multipart_upload_id'],
            input_layer_uuid=str(input_layer.uuid)
        ).exists())

    def test_check_layer(self):
        view = CheckLayer.as_view()
        # create layer by superuser
        layer_1 = InputLayerF.create(
            privacy_type=InputLayer.PrivacyTypes.PRIVATE,
            name='test_superuser_layer.tif',
            size=10,
            owner=self.superuser,
            client_id='layer-1'
        )
        # create layer by user with+without file
        layer_2 = InputLayerF.create(
            privacy_type=InputLayer.PrivacyTypes.PRIVATE,
            name='test_layer_2.tif',
            size=10,
            owner=self.user_1,
            client_id='layer-2'
        )
        layer_3 = InputLayerF.create(
            privacy_type=InputLayer.PrivacyTypes.PRIVATE,
            name='test_layer_3.tif',
            size=10,
            owner=self.user_1,
            client_id='layer-3'
        )
        file_path = absolute_path(
            'cplus_api', 'tests', 'data',
            'models', 'test_model_1.tif'
        )
        self.store_layer_file(layer_3, file_path, layer_3.name)
        # test with layer_uuid
        data = [
            str(layer_1.uuid),
            str(layer_2.uuid),
            str(layer_3.uuid),
            str(uuid.uuid4())
        ]
        request = self.factory.post(
            reverse('v1:layer-check') + '?id_type=layer_uuid',
            data, format='json'
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.user_1
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn('available', response.data)
        self.assertIn('unavailable', response.data)
        self.assertIn('invalid', response.data)
        self.assertEqual(len(response.data['invalid']), 2)
        self.assertIn(str(layer_1.uuid), response.data['invalid'])
        self.assertIn(str(layer_2.uuid), response.data['unavailable'])
        self.assertIn(str(layer_3.uuid), response.data['available'])
        # test with client id
        data = [
            layer_1.client_id,
            layer_2.client_id,
            layer_3.client_id,
            'test-layer-invalid'
        ]
        request = self.factory.post(
            reverse('v1:layer-check') + '?id_type=client_id',
            data, format='json'
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.user_1
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['invalid']), 2)
        self.assertIn('test-layer-invalid', response.data['invalid'])
        self.assertIn(layer_1.client_id, response.data['invalid'])
        self.assertIn(layer_2.client_id, response.data['unavailable'])
        self.assertIn(layer_3.client_id, response.data['available'])

    def test_convert_size(self):
        self.assertEqual(convert_size(0), '0B')
        self.assertEqual(convert_size(1024), '1.0 KB')
        self.assertEqual(convert_size(1024 * 1024), '1.0 MB')

    @mock.patch('boto3.client')
    def test_abort_multipart_upload(self, mocked_s3):
        s3_client = MockS3Client()
        mocked_s3.return_value = s3_client
        view = LayerUploadAbort.as_view()
        file_path = absolute_path(
            'cplus_api', 'tests', 'data',
            'models', 'test_model_1.tif'
        )
        base_filename = 'test_model_1_finish3.tif'
        input_layer = InputLayerF.create(
            privacy_type=InputLayer.PrivacyTypes.PRIVATE,
            name=base_filename,
            size=10
        )
        kwargs = {
            'layer_uuid': str(input_layer.uuid)
        }
        # test invalid payload
        payload = {}
        request = self.factory.post(
            reverse('v1:layer-upload-abort', kwargs=kwargs),
            data=payload, format='json'
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.superuser
        response = view(request, **kwargs)
        self.assertEqual(response.status_code, 400)
        # test success abort with returned parts = 1
        payload = {
            'multipart_upload_id': 'this_is_upload_id'
        }
        upload_record = MultipartUpload.objects.create(
            upload_id=payload['multipart_upload_id'],
            input_layer_uuid=input_layer.uuid,
            created_on=timezone.now(),
            uploader=input_layer.owner,
            parts=10
        )
        input_layer.size = os.stat(file_path).st_size
        input_layer.save(update_fields=['size'])
        request = self.factory.post(
            reverse('v1:layer-upload-abort', kwargs=kwargs),
            data=payload, format='json'
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.superuser
        response = view(request, **kwargs)
        self.assertEqual(response.status_code, 204)
        upload_record.refresh_from_db()
        self.assertTrue(upload_record.is_aborted)
        # test success abort with returned parts = 0
        s3_client.mock_parts = {
            'Parts': []
        }
        request = self.factory.post(
            reverse('v1:layer-upload-abort', kwargs=kwargs),
            data=payload, format='json'
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.superuser
        response = view(request, **kwargs)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            MultipartUpload.objects.filter(
                upload_id=payload['multipart_upload_id'],
                input_layer_uuid=input_layer.uuid
            ).exists()
        )
        self.assertFalse(
            InputLayer.objects.filter(
                uuid=input_layer.uuid
            ).exists()
        )

    @mock.patch('boto3.client')
    def test_abort_multipart_upload_with_exc(self, mocked_s3):
        s3_client = MockS3Client()
        mocked_s3.return_value = s3_client
        view = LayerUploadAbort.as_view()
        file_path = absolute_path(
            'cplus_api', 'tests', 'data',
            'models', 'test_model_1.tif'
        )
        base_filename = 'test_model_1_finish3.tif'
        input_layer = InputLayerF.create(
            privacy_type=InputLayer.PrivacyTypes.PRIVATE,
            name=base_filename,
            size=10
        )
        payload = {
            'multipart_upload_id': 'this_is_upload_id'
        }
        MultipartUpload.objects.create(
            upload_id=payload['multipart_upload_id'],
            input_layer_uuid=input_layer.uuid,
            created_on=timezone.now(),
            uploader=input_layer.owner,
            parts=10
        )
        input_layer.size = os.stat(file_path).st_size
        input_layer.save(update_fields=['size'])
        kwargs = {
            'layer_uuid': str(input_layer.uuid)
        }
        s3_client.raise_exc = True
        request = self.factory.post(
            reverse('v1:layer-upload-abort', kwargs=kwargs),
            data=payload, format='json'
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.superuser
        response = view(request, **kwargs)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            MultipartUpload.objects.filter(
                upload_id=payload['multipart_upload_id'],
                input_layer_uuid=input_layer.uuid
            ).exists()
        )
        self.assertFalse(
            InputLayer.objects.filter(
                uuid=input_layer.uuid
            ).exists()
        )

    def test_layer_fetch_by_client_id(self):
        view = FetchLayerByClientId.as_view()
        payload = [
            'ncs_pathways--Final_Alien_Invasive_Plant_priority_norm.tif'
            '_4326_20_20_1072586664'
        ]
        request = self.factory.post(
            reverse('v1:fetch-layer-by-client-id'),
            data=payload, format='json'
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.superuser
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
        input_layer = InputLayerF.create(
            privacy_type=InputLayer.PrivacyTypes.COMMON,
            client_id=payload[0]
        )
        request = self.factory.post(
            reverse('v1:fetch-layer-by-client-id'),
            data=payload, format='json'
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.user_1
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        find_layer = self.find_layer_from_response(
            response.data, input_layer.uuid)
        self.assertTrue(find_layer)
        self.assertFalse(find_layer['url'])
        self.assertFalse(input_layer.file)
        input_layer_2 = InputLayerF.create(
            privacy_type=InputLayer.PrivacyTypes.COMMON,
            client_id=payload[0]
        )
        file_path = absolute_path(
            'cplus_api', 'tests', 'data',
            'models', 'test_model_1.tif'
        )
        self.store_layer_file(
            input_layer_2, file_path, input_layer_2.name)
        request = self.factory.post(
            reverse('v1:fetch-layer-by-client-id'),
            data=payload, format='json'
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.user_1
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        find_layer = self.find_layer_from_response(
            response.data, input_layer_2.uuid)
        self.assertTrue(find_layer)
        self.assertTrue(find_layer['url'])
        self.assertEqual(find_layer['uuid'], str(input_layer_2.uuid))

    def test_reference_layer_not_exist_yet(self):
        view = ReferenceLayerDownload.as_view()
        request = self.factory.get(
            reverse('v1:reference-layer-download'),
            format='json'
        )
        request.resolver_match = FakeResolverMatchV1
        response = view(request)
        self.assertEqual(response.status_code, 404)

    def test_reference_layer_not_available(self):
        view = ReferenceLayerDownload.as_view()
        InputLayerF.create(
            privacy_type=InputLayer.PrivacyTypes.COMMON,
            component_type=InputLayer.ComponentTypes.REFERENCE_LAYER
        )
        request = self.factory.get(
            reverse('v1:reference-layer-download'),
            format='json'
        )
        request.resolver_match = FakeResolverMatchV1
        response = view(request)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.data,
            {'detail': 'Reference layer is not available.'}
        )

    def test_reference_layer_download(self):
        bbox = '29.134295060,-31.158062261,29.279926683,-31.094568889'
        view = ReferenceLayerDownload.as_view()
        reference_layer_1 = InputLayerF.create(
            privacy_type=InputLayer.PrivacyTypes.COMMON,
            component_type=InputLayer.ComponentTypes.REFERENCE_LAYER
        )
        reference_layer_2 = InputLayerF.create(
            privacy_type=InputLayer.PrivacyTypes.COMMON,
            component_type=InputLayer.ComponentTypes.REFERENCE_LAYER
        )
        file_path = absolute_path(
            'cplus_api', 'tests', 'data',
            'reference_layer.tif'
        )
        self.store_layer_file(
            reference_layer_1, file_path, reference_layer_1.name)
        self.store_layer_file(
            reference_layer_2, file_path, reference_layer_2.name)
        request = self.factory.get(
            f"{reverse('v1:reference-layer-download')}?bbox={bbox}",
            format='json'
        )
        request.resolver_match = FakeResolverMatchV1
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn('X-Accel-Redirect', response.headers)
        file_path = os.path.join(
            settings.TEMPORARY_LAYER_DIR,
            response.headers['X-Accel-Redirect'].replace('/userfiles/', '')
        )
        self.assertTrue(os.path.exists(file_path))
        # Test the streamed content
        import rasterio

        with rasterio.open(file_path) as dataset:
            expected_area = 0.01331516565230782
            bbox_polygon = Polygon.from_bbox(dataset.bounds)
            self.assertAlmostEqual(
                bbox_polygon.area,
                expected_area,
                places=3
            )
        os.remove(file_path)

    def test_pwl_layer_download(self):
        bbox = '29.134295060,-31.158062261,29.279926683,-31.094568889'
        view = DefaultLayerDownload.as_view()
        priority_layer = InputLayerF.create(
            privacy_type=InputLayer.PrivacyTypes.COMMON,
            component_type=InputLayer.ComponentTypes.PRIORITY_LAYER
        )

        file_path = absolute_path(
            'cplus_api', 'tests', 'data',
            'priority_layer.tif'
        )
        self.store_layer_file(
            priority_layer, file_path, priority_layer.name)

        kwargs = {
            'layer_uuid': str(priority_layer.uuid)
        }

        endpoint = reverse('v1:default-priority-layer-download', kwargs=kwargs)
        request = self.factory.get(f"""{endpoint}?bbox={bbox}""")
        request.resolver_match = FakeResolverMatchV1
        request.user = self.superuser
        response = view(request, **kwargs)
        self.assertEqual(response.status_code, 200)
        self.assertIn('X-Accel-Redirect', response.headers)
        file_path = os.path.join(
            settings.TEMPORARY_LAYER_DIR,
            response.headers['X-Accel-Redirect'].replace('/userfiles/', '')
        )
        self.assertTrue(os.path.exists(file_path))
        # Test the streamed content
        import rasterio

        with rasterio.open(file_path) as dataset:
            expected_area = 0.00924664281410274
            bbox_polygon = Polygon.from_bbox(dataset.bounds)
            self.assertAlmostEqual(
                bbox_polygon.area,
                expected_area,
                places=3
            )
        os.remove(file_path)
