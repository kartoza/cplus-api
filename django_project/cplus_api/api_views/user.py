from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from cplus_api.serializers.common import (
    APIErrorSerializer
)


class UserInfo(APIView):
    """API to return user info."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='user',
        responses={
            200: openapi.Schema(
                description=(
                        'Success getting user profile'
                ),
                type=openapi.TYPE_OBJECT,
                properties={
                    'trends_earth_id': openapi.Schema(
                        title='Trends Earth ID',
                        type=openapi.TYPE_STRING
                    ),
                    'username': openapi.Schema(
                        title='CPLUS API Username',
                        type=openapi.TYPE_STRING
                    ),
                    'first_name': openapi.Schema(
                        title='First Name',
                        type=openapi.TYPE_STRING
                    ),
                    'last_name': openapi.Schema(
                        title='Last Name',
                        type=openapi.TYPE_STRING
                    ),
                    'role': openapi.Schema(
                        title='User Role',
                        type=openapi.TYPE_STRING
                    ),
                },
                example={
                    "trends_earth_id": "feac0387-8fe8-41e8-af08-d7e97d30ffed",
                    "username": "feac0387-8fe8-41e8-af08-d7e97d30ffed",
                    "email": "test@domain.com",
                    "first_name": "User First Name",
                    "last_name": "User Last Name",
                    "role": "External"
                }
            ),
            400: APIErrorSerializer,
            404: APIErrorSerializer
        }
    )
    def get(self, request, *args, **kwargs):
        user = request.user
        return Response(status=200, data={
            'trends_earth_id': user.username,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': user.user_profile.role.name if getattr(
                user, 'user_profile'
            ) else '',
        })
