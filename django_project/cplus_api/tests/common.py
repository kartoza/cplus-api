"""Common functions for tests."""
import os
import shutil
from collections import OrderedDict
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, TransactionTestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIRequestFactory
from cplus_api.tests.factories import UserF
from django.core.files.storage import storages
from cplus_api.models.layer import InputLayer


class DummyTask:
    def __init__(self, id):
        self.id = id


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


class BaseInitData(object):

    def init_test_data(self):
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
        # delete storage used in default and minio
        default_storage = storages['default']
        clear_test_dir(default_storage.location)
        minio_storage = storages['minio']
        clear_test_dir(minio_storage.location)

    def store_input_layer_file(self, input_layer: InputLayer, file_path):
        with open(file_path, 'rb') as output_file:
            input_layer.file.save(os.path.basename(file_path), output_file)

    def read_uploaded_file(self, file_path):
        with open(file_path, 'rb') as test_file:
            file = SimpleUploadedFile(
                content=test_file.read(),
                name=test_file.name,
                content_type='multipart/form-data'
            )
        return file


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
    """Fake class to mock versioning"""
    namespace = 'v1'
