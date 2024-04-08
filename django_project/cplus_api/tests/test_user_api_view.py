from cplus_api.api_views.user import UserInfo
from cplus_api.tests.common import FakeResolverMatchV1, BaseAPIViewTest
from cplus_api.auth import TRENDS_EARTH_PROFILE_URL
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import force_authenticate
from unittest.mock import patch
import requests_mock


class TestUserInfo(BaseAPIViewTest):
    """
    Test the UserInfo API and authenticatio using Trends.Earth JWT token
    """

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

    def test_token_exist_in_redis(self):
        """
        Test when token is provided in Authorization header and exists in Redis cache.
        User should get response status 200.
        """
        request = self.factory.get(
            reverse('v1:user-info'),
            **{'HTTP_AUTHORIZATION': f'Bearer {self.jwt_token}'}
        )
        request.resolver_match = FakeResolverMatchV1
        view = UserInfo.as_view()
        self.fake_redis.set(self.jwt_token, self.user.id)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['detail'], 'OK')

    def test_token_not_exist_in_trends_earth(self):
        """
        Test when token is provided in Authorization header but not exists in Redis cache,
        and does not exist in Trends.Earth API.
        """
        request = self.factory.get(
            reverse('v1:user-info'),
            **{'HTTP_AUTHORIZATION': f'Bearer {self.jwt_token}'}
        )
        request.resolver_match = FakeResolverMatchV1
        view = UserInfo.as_view()
        self.fake_redis.delete(self.jwt_token)

        with requests_mock.Mocker() as rm:
            return_value = {
                "description": "Signature has expired",
                "error": "Invalid token",
                "status_code": 401
            }
            rm.get(TRENDS_EARTH_PROFILE_URL, json=return_value, status_code=401)
            response = view(request)
            self.assertEqual(response.status_code, 403)

    def test_token_exist_in_trends_earth(self):
        """
        Test when token is provided in Authorization header but not exists in Redis cache,
        and it exists in Trends.Earth API.
        """
        request = self.factory.get(
            reverse('v1:user-info'),
            **{'HTTP_AUTHORIZATION': f'Bearer {self.jwt_token}'}
        )
        request.resolver_match = FakeResolverMatchV1
        view = UserInfo.as_view()
        self.fake_redis.delete(self.jwt_token)

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
            created_user = get_user_model().objects.get(username=return_value['data']['id'])
            self.assertEqual(created_user.email, return_value['data']['email'])
            self.assertEqual(created_user.first_name, return_value['data']['name'])
            self.assertEqual(created_user.user_profile.role.name, 'External')
