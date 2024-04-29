import logging
from datetime import timedelta
from celery import shared_task
from django.utils import timezone

from cplus_api.models import InputLayer, OutputLayer, UserProfile

logger = logging.getLogger(__name__)


@shared_task(name="remove_layers")
def remove_layers():
    """
    Remove layer that has been more than 2 weeks.
    """
    ext_users = UserProfile.objects.exclude(
        role__name='Internal'
    ).values_list('user', flat=True)

    results = {
        InputLayer: 0,
        OutputLayer: 0
    }

    last_14_days_datetime = timezone.now() - timedelta(days=14)

    for LayerClass in [InputLayer, OutputLayer]:
        if LayerClass == InputLayer:
            layers = InputLayer.objects.filter(
                owner__in=ext_users,
                created_on__lt=last_14_days_datetime
            )
        else:
            layers = OutputLayer.objects.filter(
                owner__in=ext_users,
                is_final_output=False,
                created_on__lt=last_14_days_datetime
            )

        for layer in layers:
            logger.info(layer)
            # do we only delete the file, or also the record from DB?
            layer.delete()
            results[LayerClass] += 1

    logger.info(f'Removed {results}')


if __name__ == '__main__':
    remove_layers()
