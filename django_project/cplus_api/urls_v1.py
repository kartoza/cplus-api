from django.urls import path
from cplus_api.api_views.user import UserInfo


# USER API
user_urls = [
    path(
        'user/me',
        UserInfo.as_view(),
        name='user-info'
    )
]

urlpatterns = []
urlpatterns += user_urls
