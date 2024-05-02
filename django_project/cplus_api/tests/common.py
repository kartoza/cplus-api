"""Common functions for tests."""
import os
import shutil
import unittest
from botocore.exceptions import ClientError
from collections import OrderedDict
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, TransactionTestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIRequestFactory
from cplus_api.models.profile import UserRoleType
from cplus_api.tests.factories import UserF
from django.core.files.storage import storages
from cplus_api.models.layer import InputLayer, OutputLayer


class DummyTask:
    def __init__(self, id):
        self.id = id


class MockS3Client:
    def __init__(self) -> None:
        self.raise_exc = False

    def generate_presigned_url(self, ClientMethod, Params, ExpiresIn):
        if self.raise_exc:
            raise ClientError(
                {
                    'Error': {
                        'Code': '123',
                        'Message': 'this_is_error'
                    }
                },
                'put_object'
            )
        return 'this_is_url'

    def create_multipart_upload(self, Bucket, Key):
        return {
            'UploadId': 'this_is_upload_id'
        }

    def complete_multipart_upload(self, Bucket, Key,
                                  MultipartUpload, UploadId):
        return True


def mocked_process(*args, **kwargs):
    return DummyTask('1')


def mocked_cache_get(self, *args, **kwargs):
    return OrderedDict()


def mocked_cache_delete(self, *args, **kwargs):
    return True


def mocked_cache_set(self, *args, **kwargs):
    pass


def clear_test_dir(path):
    try:
        if os.path.exists(path):
            shutil.rmtree(path)
    except Exception:
        pass


class BaseInitData(unittest.TestCase):

    def init_test_data(self):
        """Provide common data for testing."""
        self.factory = APIRequestFactory()
        self.superuser = UserF.create(
            is_staff=True,
            is_superuser=True,
            is_active=True
        )
        self.user_1 = UserF.create(
            is_active=True
        )
        self.scenario_task_ct = ContentType.objects.get(
            app_label="cplus_api", model="scenariotask")

    def cleanup(self):
        """Delete storage used in default and minio."""
        default_storage = storages['default']
        clear_test_dir(default_storage.location)
        minio_storage = storages['input_layer_storage']
        clear_test_dir(minio_storage.location)

    def store_layer_file(self, layer: InputLayer | OutputLayer,
                         file_path, file_name=None):
        """Store existing file_path to layer filefield."""
        name = file_name if file_name else os.path.basename(file_path)
        with open(file_path, 'rb') as output_file:
            layer.file.save(name, output_file)

    def read_uploaded_file(self, file_path):
        """Return file for data upload."""
        with open(file_path, 'rb') as test_file:
            file = SimpleUploadedFile(
                content=test_file.read(),
                name=test_file.name,
                content_type='multipart/form-data'
            )
        return file

    def direct_upload_layer_file(self, src_file_path, dest_file_path):
        """Direct copy/upload existing src_file_path to dest_file_path."""
        dir_name, _ = os.path.split(dest_file_path)
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
        shutil.copyfile(src_file_path, dest_file_path)

    def check_validation_error_string(self, data, message):
        """Assert if message is in validation error response."""
        self.assertIn('detail', data)
        details = data['detail']
        if isinstance(details, list):
            filtered = [x for x in details if message in x]
            self.assertTrue(filtered)
        else:
            self.assertIn(message, details)

    def create_internal_user(self):
        """Create a new user with internal role."""
        user = UserF.create()
        role, _ = UserRoleType.objects.get_or_create(
            name='Internal',
            defaults={
                'description': 'Internal  user'
            }
        )
        user.user_profile.role = role
        user.user_profile.save()
        return user

    def find_layer_from_response(self, layers, layer_uuid):
        """Find layer (input/output) from response data."""
        find_layer = [
            layer for layer in layers if
            layer['uuid'] == str(layer_uuid)
        ]
        return find_layer[0] if len(find_layer) > 0 else None


class BaseAPIViewTest(BaseInitData, TestCase):

    def setUp(self):
        self.init_test_data()

    @classmethod
    def tearDownClass(cls):
        super().cleanup(cls)
        super().tearDownClass()


class BaseAPIViewTransactionTest(BaseInitData, TransactionTestCase):
    """
    This base class is for test classes that needs django-cleanup.

    See: https://github.com/un1t/django-cleanup?tab=readme-ov-file#
    how-to-write-tests
    """

    def setUp(self):
        self.init_test_data()

    @classmethod
    def tearDownClass(cls):
        super().cleanup(cls)
        super().tearDownClass()


class FakeResolverMatchV1:
    """Fake class to mock versioning."""
    namespace = 'v1'
