"""Task to remove resources."""

from celery import shared_task
import logging


logger = logging.getLogger(__name__)
# remove tasks with two months old
REMOVE_AFTER_DAYS = 60


@shared_task(name="check_celery_background_tasks")
def check_celery_background_tasks():
    logger.info('Triggered check_celery_background_tasks')
