import os
import math
from datetime import timedelta
from rest_framework.exceptions import PermissionDenied
from drf_yasg import openapi
from minio import Minio
from minio.error import S3Error
from django.conf import settings
from django.contrib.sites.models import Site
from core.models.preferences import SitePreferences
from cplus_api.models.scenario import ScenarioTask


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
PARAMS_PAGINATION = [
    openapi.Parameter(
        'page', openapi.IN_QUERY,
        description='Page number in pagination',
        type=openapi.TYPE_INTEGER,
        default=1
    ), openapi.Parameter(
        'page_size', openapi.IN_QUERY,
        description='Total records in a page',
        type=openapi.TYPE_INTEGER,
        minimum=1,
        maximum=50,
        default=50
    )
]


class BaseScenarioReadAccess(object):
    """Base class to validate whether user can access the scenario."""

    def validate_user_access(self, user, scenario_task: ScenarioTask,
                             method='access'):
        if user.is_superuser:
            return
        if scenario_task.submitted_by != user:
            raise PermissionDenied(
                f'You are not allowed to {method} '
                f'scenario {str(scenario_task.uuid)}!')


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


def build_minio_absolute_url(url):
    minio_site = Site.objects.filter(
        name__icontains='minio api'
    ).first()
    current_site = minio_site if minio_site else Site.objects.get_current()
    scheme = 'https://'
    if settings.DEBUG:
        scheme = 'http://'
    domain = current_site.domain
    if not domain.endswith('/'):
        domain = domain + '/'
    result = url.replace('http://minio:9000/', f'{scheme}{domain}')
    return result


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
            os.environ.get("MINIO_BUCKET_NAME"), filename,
            expires=timedelta(hours=3))
        return build_minio_absolute_url(upload_url)
    except S3Error:
        return None


def convert_size(size_bytes):
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return "%s %s" % (s, size_name[i])
