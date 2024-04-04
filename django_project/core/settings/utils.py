# -*- coding: utf-8 -*-
"""Utilities for project."""
import os
import uuid
import json

# Absolute filesystem path to the Django project directory:
DJANGO_ROOT = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    ))


def absolute_path(*args):
    """Return absolute path of django project."""
    return os.path.join(DJANGO_ROOT, *args)


def ensure_secret_key_file():
    """Checks that secret.py exists in settings dir.

    If not, creates one with a random generated SECRET_KEY setting."""
    secret_path = absolute_path('core', 'settings', 'secret.py')
    if not os.path.exists(secret_path):
        from django.utils.crypto import get_random_string
        secret_key = get_random_string(
            50, 'abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)')
        with open(secret_path, 'w') as f:
            f.write("SECRET_KEY = " + repr(secret_key) + "\n")


def code_release_version():
    """ Read code release version from file."""
    version = absolute_path('version', 'version.txt')
    if os.path.exists(version):
        version = (open(version, 'rb').read()).decode("utf-8")
        if version:
            return version
    return '0.0.1'


class UUIDEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, uuid.UUID):
            # if the obj is uuid, we simply return the value of uuid
            return obj.hex
        return json.JSONEncoder.default(self, obj)


# Import the secret key
ensure_secret_key_file()
