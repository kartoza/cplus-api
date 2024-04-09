import requests
import jwt
import fakeredis
from core.celery import BASE_REDIS_URL
from datetime import datetime
from django.contrib.auth import get_user_model
from django.db import connection
from redis import Redis
from rest_framework import authentication
from rest_framework import exceptions



TRENDS_EARTH_PROFILE_URL = 'https://api2.trends.earth/api/v1/user/me'


db_name = connection.settings_dict['NAME']
if db_name.startswith('test_'):
    redis = Redis.from_url(BASE_REDIS_URL[0])
else:
    redis = fakeredis.FakeStrictRedis()


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
        user_id = redis.get(token)
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

                redis.set(
                    token, user.id
                )
                expiry = (
                    datetime.fromtimestamp(
                        decoded_token['exp']
                    ) - datetime.now()
                ).seconds
                redis.expire(
                    token,
                    expiry
                )
                return user, None
            raise exceptions.AuthenticationFailed('No such user')
