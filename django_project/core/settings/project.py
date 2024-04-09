# coding=utf-8

"""Project level settings.

Adjust these values as needed but don't commit passwords etc. to any public
repository!
"""
import os  # noqa

from django.db import connection
from .contrib import *  # noqa
from .utils import code_release_version

ALLOWED_HOSTS = ['*']
ADMINS = (
    ('Dimas Ciputra', 'dimas@kartoza.com'),
)
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': os.environ['DATABASE_NAME'],
        'USER': os.environ['DATABASE_USERNAME'],
        'PASSWORD': os.environ['DATABASE_PASSWORD'],
        'HOST': os.environ['DATABASE_HOST'],
        'PORT': 5432,
        'TEST_NAME': 'unittests',
    }
}

# Set debug to false for production
DEBUG = TEMPLATE_DEBUG = False

# Extra installed apps
INSTALLED_APPS = INSTALLED_APPS + (
    'core',
    'cplus',
    'cplus_api'
)

# use custom filter to hide other sensitive informations
DEFAULT_EXCEPTION_REPORTER_FILTER = (
    'core.settings.filter.ExtendSafeExceptionReporterFilter'
)

CODE_RELEASE_VERSION = code_release_version()

# s3
# TODO: set CacheControl in object_parameters+endpoint_url
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
          "access_key": os.environ.get("S3_AWS_ACCESS_KEY_ID"),
          "secret_key": os.environ.get("S3_AWS_SECRET_ACCESS_KEY"),
          "bucket_name": "cplus",
          "file_overwrite": False,
          "max_memory_size": 300 * 1024 * 1024,  # 300MB
          "endpoint_url": os.environ.get("AWS_S3_ENDPOINT"),
          "session_profile": None
        },
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
    },
    "minio": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
          "access_key": os.environ.get("MINIO_ACCESS_KEY_ID"),
          "secret_key": os.environ.get("MINIO_SECRET_ACCESS_KEY"),
          "bucket_name": "cplus",
          "file_overwrite": False,
          "max_memory_size": 300 * 1024 * 1024,  # 300MB
          "endpoint_url": os.environ.get("MINIO_ENDPOINT"),
        },
    },
}
