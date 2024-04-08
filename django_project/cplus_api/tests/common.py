"""Common functions for tests."""
from collections import OrderedDict
from cplus_api.auth import redis
from cplus_api.tests.factories import UserF
from django.test import TestCase
from rest_framework.test import APIRequestFactory
from unittest.mock import patch


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
        self.user = UserF.create(
            username='c942182c-f3d3-4e3b-80a5-aa7fd9494d00'
        )
        self.jwt_token = (
            'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.'
            'eyJpc3MiOiJPbmxpbmUgSldUIEJ1aWxkZXIiLCJpYXQiOjE3MTI1NDIxOTYsImV4cCI6MTc0NDA3'
            'ODE5NiwiYXVkIjoid3d3LmV4YW1wbGUuY29tIiwic3ViIjoianJvY2tldEBleGFtcGxlLmNvbSIsI'
            'kdpdmVuTmFtZSI6IkpvaG5ueSIsIlN1cm5hbWUiOiJSb2NrZXQiLCJFbWFpbCI6Impyb2NrZXRAZXh'
            'hbXBsZS5jb20iLCJSb2xlIjpbIk1hbmFnZXIiLCJQcm9qZWN0IEFkbWluaXN0cmF0b3IiXX0.'
            '_Z5NTnVbB4OT4iJREx9A-9JC1_Si-aBWG1nq6SQapAU'
        )
        self.fake_redis = redis
        super().setUp()

    def trends_earth_authenticate(self):
        self.fake_redis.set(self.jwt_token, self.user.id)


class FakeResolverMatchV1:
    """Fake class to mock versioning"""
    namespace = 'v1'
