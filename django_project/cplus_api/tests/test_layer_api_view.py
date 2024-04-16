import os
from django.urls import reverse
from rest_framework.exceptions import PermissionDenied
from core.settings.utils import absolute_path
from cplus_api.api_views.layer import (
    LayerList,
    LayerDetail,
    LayerUpload,
    LayerUploadStart,
    LayerUploadFinish
)
from cplus_api.models.layer import (
    InputLayer,
    input_layer_dir_path,
    select_input_layer_storage
)
from cplus_api.tests.common import (
    FakeResolverMatchV1,
    BaseAPIViewTransactionTest
)
from cplus_api.tests.factories import InputLayerF


class TestLayerAPIView(BaseAPIViewTransactionTest):

    def find_layer_from_response(self, layers, layer_uuid):
        find_layer = [
            layer for layer in layers if
            layer['uuid'] == str(layer_uuid)
        ]
        return find_layer[0] if len(find_layer) > 0 else None


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
        self.assertFalse(
            input_layer.file.storage.exists(input_layer.file.name))
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
        self.store_input_layer_file(input_layer, file_path)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)
        find_layer = self.find_layer_from_response(
            response.data['results'], input_layer.uuid)
        self.assertTrue(find_layer)
        self.assertTrue(find_layer['url'])

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
        layer_detail_view = LayerDetail()
        self.assertTrue(layer_detail_view.validate_layer_access(
            input_layer_1, self.superuser
        ))
        self.assertTrue(layer_detail_view.validate_layer_access(
            input_layer_1, self.user_1
        ))
        self.assertTrue(layer_detail_view.validate_layer_access(
            input_layer_2, self.user_1
        ))
        self.assertFalse(layer_detail_view.validate_layer_access(
            input_layer_3, self.user_1
        ))
        self.assertTrue(layer_detail_view.validate_layer_access(
            input_layer_3, input_layer_3.owner
        ))
        # upload access
        layer_upload_view = LayerUpload()
        self.assertTrue(layer_upload_view.validate_upload_access(
            InputLayer.PrivacyTypes.COMMON, self.superuser
        ))
        self.assertTrue(layer_upload_view.validate_upload_access(
            InputLayer.PrivacyTypes.INTERNAL, self.user_1
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
        self.store_input_layer_file(input_layer, file_path)
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

    def test_layer_delete(self):
        view = LayerDetail.as_view()
        input_layer = InputLayerF.create(
            privacy_type=InputLayer.PrivacyTypes.PRIVATE
        )
        file_path = absolute_path(
            'cplus_api', 'tests', 'data',
            'models', 'test_model_1.tif'
        )
        self.store_input_layer_file(input_layer, file_path)
        layer_uuid = input_layer.uuid
        layer_filename = input_layer.file.name
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
        self.assertFalse(
            input_layer.file.storage.exists(layer_filename)
        )

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
        self.assertTrue(
            input_layer.file.storage.exists(input_layer.file.name))
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

    def test_layer_upload_start(self):
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
        self.assertIn('upload_url', response.data)
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
        self.store_input_layer_file(
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
        # file not exist
        request = self.factory.get(
            reverse('v1:layer-upload-finish', kwargs=kwargs)
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
        request = self.factory.get(
            reverse('v1:layer-upload-finish', kwargs=kwargs)
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
        request = self.factory.get(
            reverse('v1:layer-upload-finish', kwargs=kwargs)
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.superuser
        response = view(request, **kwargs)
        self.assertEqual(response.status_code, 200)
        input_layer.refresh_from_db()
        self.assertTrue(input_layer.file.name)
        self.assertTrue(
            input_layer.file.storage.exists(input_layer.file.name))
