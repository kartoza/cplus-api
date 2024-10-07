import json
import logging
import os
import traceback
from datetime import datetime
from uuid import UUID
from enum import Enum

import boto3
import math
from botocore.client import Config
from botocore.exceptions import ClientError
from django.conf import settings
from django.contrib.sites.models import Site
from drf_yasg import openapi
from rest_framework.exceptions import PermissionDenied

from core.models.preferences import SitePreferences
from cplus_api.models.scenario import ScenarioTask

logger = logging.getLogger(__name__)
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

    def validate_user_access(
            self, user, scenario_task: ScenarioTask, method='access'):
        """Validate user access when accessing a scenario task.

        :param user: Logged in User
        :type user: User object
        :param scenario_task: scenario task object
        :type scenario_task: ScenarioTask
        :param method: access type, defaults to 'access'
        :type method: str, optional
        :raises PermissionDenied: when user does not have no permission to
            access the scenario task
        """
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
    """Build minio absoulte URL only for Dev/DEBUG env.

    :param url: url
    :type url: str
    :return: url with absolute base url
    :rtype: str
    """
    if not settings.DEBUG:
        return url
    minio_site = Site.objects.filter(
        name__icontains='minio api'
    ).first()
    current_site = minio_site if minio_site else Site.objects.get_current()
    scheme = 'http://'
    domain = current_site.domain
    if not domain.endswith('/'):
        domain = domain + '/'
    return url.replace('http://minio:9000/', f'{scheme}{domain}')


def get_upload_client():
    """Get s3 client object to upload.

    :return: s3 client
    :rtype: any
    """
    # Initialize upload client
    if settings.DEBUG:
        upload_client = boto3.client(
            's3',
            endpoint_url=os.environ.get("MINIO_ENDPOINT", ""),
            aws_access_key_id=os.environ.get("MINIO_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("MINIO_SECRET_ACCESS_KEY"),
            config=Config(signature_version='s3v4'),
            verify=False
        )
    else:
        upload_client = boto3.client(
            's3', config=Config(signature_version='s3v4'))
    return upload_client


def get_presigned_url(filename):
    """Generate presigned url of upload.

    :param filename: file name
    :type filename: str
    :return: presigned url
    :rtype: str
    """
    upload_client = get_upload_client()
    bucket_name = os.environ.get("MINIO_BUCKET_NAME")
    try:
        method_parameters = {
            'Bucket': bucket_name,
            'Key': filename
        }
        response = upload_client.generate_presigned_url(
            ClientMethod='put_object',
            Params=method_parameters,
            ExpiresIn=3600 * 3)
    except ClientError as exc:
        logger.error(f'Unexpected exception occured: {type(exc).__name__} '
                     'in get_presigned_url')
        logger.error(exc)
        logger.error(traceback.format_exc())
        return None

    # The response contains the presigned URL
    return build_minio_absolute_url(response)


def get_multipart_presigned_urls(filename, parts):
    """Generate presigned urls for a file.

    :param filename: file name
    :type filename: str
    :param parts: number of parts that will be uploaded
    :type parts: int
    :return: Tuple of Multipart UploadId and presigned_urls
    :rtype: tuple
    """
    upload_client = get_upload_client()
    bucket_name = os.environ.get("MINIO_BUCKET_NAME")
    response = upload_client.create_multipart_upload(
        Bucket=bucket_name,
        Key=filename
    )
    upload_id = response['UploadId']
    results = []
    for i in range(0, parts):
        part_number = i + 1
        method_parameters = {
            'Bucket': bucket_name,
            'Key': filename,
            'UploadId': upload_id,
            'PartNumber': part_number
        }
        single_url = upload_client.generate_presigned_url(
            ClientMethod='upload_part',
            Params=method_parameters,
            ExpiresIn=3600 * 3
        )
        results.append({
            'part_number': part_number,
            'url': build_minio_absolute_url(single_url)
        })
    return upload_id, results


def complete_multipart_upload(filename, upload_id, parts):
    """Mark multipart upload as completed.

    :param filename: file name
    :type filename: str
    :param upload_id: Multipart UploadId
    :type upload_id: str
    :param parts: Dictionary of etag and part_number
    :type parts: dict
    :return: True
    :rtype: bool
    """
    upload_client = get_upload_client()
    bucket_name = os.environ.get("MINIO_BUCKET_NAME")
    # sort parts by part_number
    sorted_parts = sorted(parts, key=lambda d: d['part_number'])
    payloads = [{
        'ETag': p['etag'],
        'PartNumber': p['part_number']
    } for p in sorted_parts]
    upload_client.complete_multipart_upload(
        Bucket=bucket_name,
        Key=filename,
        MultipartUpload={
            'Parts': payloads
        },
        UploadId=upload_id
    )
    return True


def abort_multipart_upload(filename, upload_id):
    """Abort multipart upload and return the part list.

    :param filename: file name
    :type filename: str
    :param upload_id: Multipart UploadId
    :type upload_id: str
    :return: total part number that has been uploaded
    :rtype: int
    """
    upload_client = get_upload_client()
    bucket_name = os.environ.get("MINIO_BUCKET_NAME")
    parts = 0
    try:
        upload_client.abort_multipart_upload(
            Bucket=bucket_name,
            Key=filename,
            UploadId=upload_id
        )
    except Exception as exc:
        logger.error(f'Unexpected exception occured: {type(exc).__name__} '
                     'in abort_multipart_upload')
        logger.error(exc)
        logger.error(traceback.format_exc())
    try:
        response = upload_client.list_parts(
            Bucket=bucket_name,
            Key=filename,
            UploadId=upload_id
        )
        part_list = response.get('Parts', [])
        parts = len(part_list)
    except Exception:
        # ignore if no such upload
        parts = 0
    return parts


def convert_size(size_bytes):
    """Convert byte size to humand readable text.

    :param size_bytes: byte sizse
    :type size_bytes: int
    :return: human readable text
    :rtype: str
    """
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return "%s %s" % (s, size_name[i])


class CustomJsonEncoder(json.JSONEncoder):
    """Class for custom object encoding."""

    def default(self, obj):
        """Custom object encoding when converting to json.

        :param obj: object to be converted
        :type obj: any
        :return: json value
        :rtype: any
        """
        if isinstance(obj, UUID):
            # if the obj is uuid, we simply return the value of uuid
            return str(obj)
        if isinstance(obj, datetime):
            # if the obj is uuid, we simply return the value of uuid
            return obj.isoformat()
        return json.JSONEncoder.default(self, obj)


def todict(obj, classkey=None):
    """Convert object to dictionary.

    :param obj: Object to be converted
    :type obj: any
    :param classkey: class definition, defaults to None
    :type classkey: any, optional
    :return: dictionary
    :rtype: dict
    """
    if isinstance(obj, Enum):
        return obj.value
    elif isinstance(obj, dict):
        data = {}
        for (k, v) in obj.items():
            data[k] = todict(v, classkey)
        return data
    elif hasattr(obj, "_ast"):
        return todict(obj._ast())
    elif hasattr(obj, "__iter__") and not isinstance(obj, str):
        return [todict(v, classkey) for v in obj]
    elif hasattr(obj, "__dict__"):
        data = dict(
            [(key, todict(value, classkey))
             for key, value in obj.__dict__.items()
             if not callable(value) and not key.startswith('_')]
        )
        if classkey is not None and hasattr(obj, "__class__"):
            data[classkey] = obj.__class__.__name__
        return data
    else:
        return obj


def get_layer_type(file_path: str):
    """Get layer type code from file path.

    :param file_path: layer file path
    :type file_path: str
    :return: layer type
    :rtype: int
    """
    file_name, file_extension = os.path.splitext(file_path)
    if file_extension.lower() in ['.tif', '.tiff']:
        return 0
    elif file_extension.lower() in ['.geojson', '.zip', '.shp']:
        return 1
    else:
        return -1
