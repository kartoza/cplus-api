import os
from django.urls import reverse
from core.settings.utils import absolute_path
from django.core.files.uploadedfile import SimpleUploadedFile
from cplus_api.api_views.layer import (
    LayerList,
    LayerDetail,
    LayerUpload
)
from cplus_api.models.layer import InputLayer
from cplus_api.tests.common import (
    FakeResolverMatchV1,
    BaseAPIViewTransactionTest
)
from cplus_api.tests.factories import InputLayerF


class TestUserInfo(BaseAPIViewTransactionTest):

    def store_input_layer_file(self, input_layer: InputLayer, file_path):
        with open(file_path, 'rb') as output_file:
            input_layer.file.save(os.path.basename(file_path), output_file)

    def find_layer_from_response(self, layers, layer_uuid):
        find_layer = [
            layer for layer in layers if
            layer['uuid'] == str(layer_uuid)
        ]
        return find_layer[0] if len(find_layer) > 0 else None

    def read_uploaded_file(self, file_path):
        with open(file_path, 'rb') as test_file:
            file = SimpleUploadedFile(
                content=test_file.read(),
                name=test_file.name,
                content_type='multipart/form-data'
            )
        return file

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
        # non existing file in storage
        input_layer.file.name = (
            'common_layers/ncs_pathway/test_model_2_123.tif'
        )
        input_layer.save()
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
        self.assertFalse(layer_upload_view.validate_upload_access(
            InputLayer.PrivacyTypes.COMMON, self.user_1
        ))
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
        view = LayerDetail.as_view()
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
        view = LayerDetail.as_view()
        response = view(request, **kwargs)
        self.assertEqual(response.status_code, 403)

    def test_layer_delete(self):
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
        view = LayerDetail.as_view()
        response = view(request, **kwargs)
        self.assertEqual(response.status_code, 403)
        # successful
        request = self.factory.delete(
            reverse('v1:layer-detail', kwargs=kwargs)
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.superuser
        view = LayerDetail.as_view()
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
        view = LayerUpload.as_view()
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
        view = LayerUpload.as_view()
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
        view = LayerUpload.as_view()
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
        view = LayerUpload.as_view()
        response = view(request)
        self.assertEqual(response.status_code, 201)
        self.assertIn('uuid', response.data)
        input_layer.refresh_from_db()
        self.assertEqual(input_layer.privacy_type, data['privacy_type'])
