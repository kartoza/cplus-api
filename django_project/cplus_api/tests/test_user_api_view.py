from django.urls import reverse
from cplus_api.api_views.user import UserInfo
from cplus_api.tests.common import FakeResolverMatchV1, BaseAPIViewTest


class TestUserInfo(BaseAPIViewTest):

    def test_user_info(self):
        request = self.factory.get(
            reverse('v1:user-info')
        )
        request.resolver_match = FakeResolverMatchV1
        view = UserInfo.as_view()
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['detail'], 'OK')
