
from .project import *  # noqa

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

# aws s3 dev configuration
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
          "bucket_name": "cplus",
          "endpoint_url": "http://s3:9000",
          "file_overwrite": False,
          "max_memory_size": 300 * 1024 * 1024,  # 300MB
        },
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
    },
}
