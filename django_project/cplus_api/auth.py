import requests
import jwt
from datetime import datetime
from django.core.cache import cache
from django.contrib.auth import get_user_model
from rest_framework import authentication
from rest_framework import exceptions


TRENDS_EARTH_PROFILE_URL = 'https://api2.trends.earth/api/v1/user/me'


class TrendsEarthAuthentication(authentication.BaseAuthentication):
    """
    Authentication class that authenticate using Trends.Earth JWT
    """
    def authenticate(self, request):
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].replace('Bearer ', '')
        else:
            raise exceptions.AuthenticationFailed(
                'Authentication credentials were not provided.'
                '')

        # Check if token exist in redis, return the user if exist
        user_id = cache.get(token)
        if user_id:
            user = get_user_model().objects.get(id=user_id)
            return user, None
        else:
            # if it does not exist, check if the token could be used to
            # get user profile from Trends.Earth
            response = requests.get(
                TRENDS_EARTH_PROFILE_URL,
                headers={'Authorization': 'Bearer ' + token}
            )

            # If profile exist, save the user and add to redis
            if response.ok:
                user_profile = response.json()['data']

                # decode token to get expiry datetime
                decoded_token = jwt.decode(
                    token, '', algorithms='HS256',
                    options={"verify_signature": False}
                )

                # create user based on the user profile
                # We use Trends.Earth id, which is a UUID Field,
                # as username in CPLUS API user table
                user, created = get_user_model().objects.get_or_create(
                    username=user_profile['id'],
                    email=user_profile['email'],
                    first_name=user_profile['name']
                )
                expiry = (
                    datetime.fromtimestamp(
                        decoded_token['exp']
                    ) - datetime.now()
                ).seconds
                cache.set(token, user.id, expiry)
                return user, None
            raise exceptions.AuthenticationFailed('No such user')
