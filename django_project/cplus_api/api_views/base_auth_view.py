from rest_framework.views import APIView
from cplus_api.auth import TrendsEarthAuthentication


class BaseAuthView(APIView):
    """
    Base class for API View that uses Trends.Earth authentication
    """
    authentication_classes = [TrendsEarthAuthentication]
