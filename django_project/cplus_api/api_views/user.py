from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from cplus_api.api_views.base_auth_view import BaseAuthView


class UserInfo(BaseAuthView):
    """API to return user info."""
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response(status=200, data={
            'detail': 'OK'
        })
