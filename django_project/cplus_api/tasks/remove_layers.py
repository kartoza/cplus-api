import logging
from datetime import timedelta
from celery import shared_task
from django.utils import timezone
from django.db.models import Q

from core.models.preferences import SitePreferences
from cplus_api.models import (
    InputLayer, OutputLayer, MultipartUpload,
    TemporaryLayer,
    input_layer_dir_path
)
from cplus_api.utils.api_helper import (
    abort_multipart_upload
)

logger = logging.getLogger(__name__)


@shared_task(name="remove_layers")
def remove_layers():
    """
    Remove layer that has been more than 2 weeks.
    """
    results = {
        InputLayer: 0,
        OutputLayer: 0,
        TemporaryLayer: 0
    }

    # Remove private Input Layer that is more 2 weeks
    last_x_days_datetime = (
        timezone.now() -
        timedelta(days=SitePreferences.preferences().layer_days_to_keep)
    )
    input_layers = InputLayer.objects.filter(
        privacy_type=InputLayer.PrivacyTypes.PRIVATE,
    ).filter(
        (
            Q(created_on__lt=last_x_days_datetime) &
            Q(last_used_on__isnull=True)
        ) |
        Q(last_used_on__lt=last_x_days_datetime)
    )
    results[InputLayer] = input_layers.count()
    input_layers.delete()

    # Remove private data that is more 2 weeks
    output_group_to_keep = SitePreferences.preferences().output_group_to_keep
    output_layers = OutputLayer.objects.filter(
        created_on__lt=last_x_days_datetime
    ).exclude(
        Q(is_final_output=True) | Q(group__in=output_group_to_keep)
    )
    results[OutputLayer] = output_layers.count()
    output_layers.delete()

    # Remove temporary layer after a day
    last_x_days_datetime = (
        timezone.now() -
        timedelta(days=1)
    )
    temp_layers = TemporaryLayer.objects.filter(
        created_on__lte=last_x_days_datetime
    )
    results[TemporaryLayer] = temp_layers.count()
    temp_layers.delete()

    logger.info(f'Removed {results}')


@shared_task(name="clean_multipart_upload")
def clean_multipart_upload():
    """
    Remove aborted layers.
    """
    last_7_days_datetime = timezone.now() - timedelta(days=7)
    last_1_days_datetime = timezone.now() - timedelta(days=1)
    uploads = MultipartUpload.objects.filter(
        Q(
            created_on__lt=last_7_days_datetime,
            is_aborted=False
        ) | Q(
            created_on__lt=last_1_days_datetime,
            is_aborted=True
        )
    )
    for upload in uploads.iterator(chunk_size=1):
        input_layer = InputLayer.objects.filter(
            uuid=upload.input_layer_uuid
        ).first()
        if input_layer is None:
            upload.delete()
            continue
        file_path = input_layer_dir_path(input_layer, input_layer.name)
        parts = abort_multipart_upload(
            file_path,
            upload.upload_id
        )
        if parts == 0:
            upload.delete()
            input_layer.delete()
        else:
            upload.is_aborted = True
            upload.save()
