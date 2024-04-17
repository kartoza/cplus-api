from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class UserInfo(APIView):
    """API to return user info."""
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response(status=200, data={
            'detail': 'OK'
        })
