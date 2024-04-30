from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class UserInfo(APIView):
    """API to return user info."""
    permission_classes = [IsAuthenticated]

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
