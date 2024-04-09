from .dev import *  # noqa

CACHES = {
    'default': {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache"
    }
}

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {
          "location": "/home/web/media/default_test",
        },
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
    },
    "minio": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {
          "location": "/home/web/media/minio_test",
        },
    },
}

