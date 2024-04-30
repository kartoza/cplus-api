import logging
from datetime import timedelta
from celery import shared_task
from django.utils import timezone
from django.db.models import Q

from core.models.preferences import SitePreferences
from cplus_api.models import InputLayer, OutputLayer

logger = logging.getLogger(__name__)


@shared_task(name="remove_layers")
def remove_layers():
    """
    Remove layer that has been more than 2 weeks.
    """
    results = {
        InputLayer: 0,
        OutputLayer: 0
    }

    # Remove private Input Layer that is more 2 weeks
    last_14_days_datetime = timezone.now() - timedelta(days=14)
    input_layers = InputLayer.objects.filter(
        privacy_type=InputLayer.PrivacyTypes.PRIVATE,
        created_on__lt=last_14_days_datetime
    )
    results[InputLayer] = input_layers.count()
    input_layers.delete()

    # Remove private data that is more 2 weeks
    output_group_to_keep = SitePreferences.preferences().output_group_to_keep
    output_layers = OutputLayer.objects.exclude(
        Q(is_final_output=True) | Q(group__in=output_group_to_keep)
    )
    results[OutputLayer] = output_layers.count()
    output_layers.delete()

    logger.info(f'Removed {results}')
