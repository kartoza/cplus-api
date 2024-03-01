"""Common functions for tests."""
from collections import OrderedDict
from django.test import TestCase
from rest_framework.test import APIRequestFactory


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


class BaseAPIViewTest(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()


class FakeResolverMatchV1:
    """Fake class to mock versioning"""
    namespace = 'v1'
