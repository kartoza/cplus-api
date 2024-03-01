
from .project import *  # noqa
from google.auth.credentials import AnonymousCredentials

# Set debug to True for development
DEBUG = True
TEMPLATES[0]['OPTIONS']['debug'] = True
TESTING = False
LOGGING_OUTPUT_ENABLED = DEBUG
LOGGING_LOG_SQL = DEBUG

CRISPY_FAIL_SILENTLY = not DEBUG

ALLOWED_HOSTS = ['*']

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Make sure static files storage is set to default
STATIC_FILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        # define output formats
        'verbose': {
            'format': (
                '%(levelname)s %(name)s %(asctime)s %(module)s %(process)d '
                '%(thread)d %(message)s')
        },
        'simple': {
            'format': (
                '%(name)s %(levelname)s %(filename)s L%(lineno)s: '
                '%(message)s')
        },
    },
    'handlers': {
        # console output
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
            'level': 'DEBUG',
        }
    },
    'loggers': {
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'INFO',  # switch to DEBUG to show actual SQL
        }
    },
    # root logger
    # non handled logs will propagate to the root logger
    'root': {
        'handlers': ['console'],
        'level': 'WARNING'
    }
}

# google cloud storage dev configuration
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.gcloud.GoogleCloudStorage",
        "OPTIONS": {
          "custom_endpoint": "http://127.0.0.1:4443",
          "bucket_name": "sample-bucket",
          "project_id": "test",
          "credentials": AnonymousCredentials(),
          "file_overwrite": False,
          "max_memory_size": 150 * 1024 * 1024,  # 150MB
          "blob_chunk_size": 256 * 1024 * 200  # 52 MB
        },
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
    },
}
