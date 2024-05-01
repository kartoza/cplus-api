import mock
from django.contrib.auth import get_user_model
from django.urls import reverse
from cplus_api.api_views.user import UserInfo
from cplus_api.tests.common import (
    FakeResolverMatchV1,
    BaseAPIViewTest,
)
from cplus_api.auth import TRENDS_EARTH_PROFILE_URL
from cplus_api.tests.factories import UserF
import requests_mock


class TestTrendsEarthAuth(BaseAPIViewTest):
    """
    Test the UserInfo API and authenticatio using Trends.Earth JWT token
    """

    def setUp(self):
        self.user = UserF.create(
            username='c942182c-f3d3-4e3b-80a5-aa7fd9494d00'
        )
        self.jwt_token = (
            'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.'
            'eyJpc3MiOiJPbmxpbmUgSldUIEJ1aWxkZXIiLCJpYXQiOjE3MTI1NDIxOTYsImV4cCI6MTc0NDA3'  # noqa
            'ODE5NiwiYXVkIjoid3d3LmV4YW1wbGUuY29tIiwic3ViIjoianJvY2tldEBleGFtcGxlLmNvbSIsI'  # noqa
            'kdpdmVuTmFtZSI6IkpvaG5ueSIsIlN1cm5hbWUiOiJSb2NrZXQiLCJFbWFpbCI6Impyb2NrZXRAZXh'  # noqa
            'hbXBsZS5jb20iLCJSb2xlIjpbIk1hbmFnZXIiLCJQcm9qZWN0IEFkbWluaXN0cmF0b3IiXX0.'  # noqa
            '_Z5NTnVbB4OT4iJREx9A-9JC1_Si-aBWG1nq6SQapAU'
        )
        super().setUp()

    def test_no_token_provided(self):
        """
        Test when no token is provided in Authorization header.
        User should get 403 error.
        """
        request = self.factory.get(
            reverse('v1:user-info')
        )
        request.resolver_match = FakeResolverMatchV1
        view = UserInfo.as_view()
        response = view(request)
        self.assertEqual(response.status_code, 403)

    @mock.patch('django.core.cache.cache.set')
    @mock.patch('django.core.cache.cache.get')
    def test_token_exist_in_redis(self, mocked_cache, mocked_set_cache):
        """
        Test when token is provided in Authorization header and
        exists in Redis cache. User should get response status 200.
        """
        mocked_cache.return_value = self.user.id
        request = self.factory.get(
            reverse('v1:user-info'),
            **{'HTTP_AUTHORIZATION': f'Bearer {self.jwt_token}'}
        )
        request.resolver_match = FakeResolverMatchV1
        view = UserInfo.as_view()
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['username'], self.user.username)
        self.assertEqual(response.data['trends_earth_id'], self.user.username)
        mocked_cache.assert_called_once()
        mocked_set_cache.assert_not_called()

    @mock.patch('django.core.cache.cache.set')
    @mock.patch('django.core.cache.cache.get')
    def test_token_not_exist_in_trends_earth(self, mocked_cache,
                                             mocked_set_cache):
        """
        Test when token is provided in Authorization header but
        not exists in Redis cache, and does not exist in Trends.Earth API.
        """
        mocked_cache.return_value = None
        request = self.factory.get(
            reverse('v1:user-info'),
            **{'HTTP_AUTHORIZATION': f'Bearer {self.jwt_token}'}
        )
        request.resolver_match = FakeResolverMatchV1
        view = UserInfo.as_view()

        with requests_mock.Mocker() as rm:
            return_value = {
                "description": "Signature has expired",
                "error": "Invalid token",
                "status_code": 401
            }
            rm.get(
                TRENDS_EARTH_PROFILE_URL,
                json=return_value,
                status_code=401
            )
            response = view(request)
            self.assertEqual(response.status_code, 403)
        mocked_cache.assert_called_once()
        mocked_set_cache.assert_not_called()

    @mock.patch('django.core.cache.cache.set')
    @mock.patch('django.core.cache.cache.get')
    def test_token_exist_in_trends_earth(self, mocked_cache,
                                         mocked_set_cache):
        """
        Test when token is provided in Authorization header but
        not exists in Redis cache, and it exists in Trends.Earth API.
        """
        mocked_cache.return_value = None
        request = self.factory.get(
            reverse('v1:user-info'),
            **{'HTTP_AUTHORIZATION': f'Bearer {self.jwt_token}'}
        )
        request.resolver_match = FakeResolverMatchV1
        view = UserInfo.as_view()

        with requests_mock.Mocker() as rm:
            return_value = {
                "data": {
                    "country": "Indonesia",
                    "created_at": "2024-03-12T04:33:54.029058",
                    "email": "test@kartoza.com",
                    "id": "df34cc5e-3772-4e42-8289-cb6d9abbe093",
                    "institution": "Kartoza",
                    "name": "Test User",
                    "role": "USER",
                    "updated_at": "2024-03-12T04:33:54.029065"
                }
            }
            rm.get(TRENDS_EARTH_PROFILE_URL, json=return_value)
            response = view(request)
            self.assertEqual(response.status_code, 200)
            created_user = get_user_model().objects.get(
                username=return_value['data']['id']
            )
            self.assertEqual(created_user.email, return_value['data']['email'])
            self.assertEqual(
                created_user.first_name,
                return_value['data']['name']
            )
            self.assertEqual(created_user.user_profile.role.name, 'External')
        mocked_cache.assert_called_once()
        mocked_set_cache.assert_called_once()
