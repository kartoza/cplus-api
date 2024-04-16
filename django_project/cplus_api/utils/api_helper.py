import os
import math
from datetime import timedelta
from drf_yasg import openapi
from core.models.preferences import SitePreferences
from minio import Minio
from minio.error import S3Error


LAYER_API_TAG = '01-layer'
SCENARIO_API_TAG = '02-scenario-analysis'
SCENARIO_OUTPUT_API_TAG = '03-scenario-outputs'

# API MANUAL PARAMETERS
PARAM_LAYER_UUID_IN_PATH = openapi.Parameter(
    'layer_uuid', openapi.IN_PATH,
    description='Layer UUID', type=openapi.TYPE_STRING
)
PARAM_SCENARIO_UUID_IN_PATH = openapi.Parameter(
    'scenario_uuid', openapi.IN_PATH,
    description='Scenario UUID', type=openapi.TYPE_STRING
)


def get_page_size(request):
    """
    Get page size from request if exists
    if it does not exist in request, then get default from SitePreferences
    if over the maximum allowed size, then returns the maximum
    """
    config = SitePreferences.preferences().api_config
    page_size = request.GET.get('page_size', None)
    if page_size is None:
        page_size = (
            config['default_page_size'] if 'default_page_size' in config
            else 50
        )
    else:
        page_size = int(page_size)
    max_size = config['max_page_size'] if 'max_page_size' in config else 50
    if page_size > max_size:
        page_size = max_size
    return page_size


def get_minio_client():
    # Initialize MinIO client
    minio_client = Minio(
        os.environ.get("MINIO_ENDPOINT", "").replace(
            "https://", "").replace("http://", ""),
        access_key=os.environ.get("MINIO_ACCESS_KEY_ID"),
        secret_key=os.environ.get("MINIO_SECRET_ACCESS_KEY"),
        secure=False  # Set to True if using HTTPS
    )
    return minio_client


def get_presigned_url(filename):
    try:
        minio_client = get_minio_client()
        # Generate pre-signed URL for uploading an object
        upload_url = minio_client.presigned_put_object(
            'cplus', filename, expires=timedelta(hours=3))
        return upload_url
    except S3Error:
        return None, None


def convert_size(size_bytes):
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return "%s %s" % (s, size_name[i])
