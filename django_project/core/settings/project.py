# coding=utf-8

"""Project level settings.

Adjust these values as needed but don't commit passwords etc. to any public
repository!
"""
import os  # noqa

from django.db import connection
from boto3.s3.transfer import TransferConfig
from .contrib import *  # noqa
from .utils import code_release_version, code_commit_release_version

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
CODE_COMMIT_HASH = code_commit_release_version()

# s3
# TODO: set CacheControl in object_parameters+endpoint_url
MB = 1024 ** 2
AWS_TRANSFER_CONFIG = TransferConfig(
    multipart_chunksize=512 * MB,
    use_threads=True,
    max_concurrency=10
)
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
          "bucket_name": os.environ.get("AWS_S3_BUCKET_NAME"),
          "file_overwrite": False,
          "max_memory_size": 300 * MB,  # 300MB
          "transfer_config": AWS_TRANSFER_CONFIG
        },
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
    },
    "input_layer_storage": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
          "bucket_name": os.environ.get("MINIO_BUCKET_NAME"),
          "file_overwrite": False,
          "max_memory_size": 300 * MB,  # 300MB,
          "transfer_config": AWS_TRANSFER_CONFIG
        },
    },
}
