"""Task to remove resources."""

from celery import shared_task
import logging
from core.models.preferences import SitePreferences


logger = logging.getLogger(__name__)

@shared_task(name="check_celery_background_tasks")
def check_celery_background_tasks():
    config = SitePreferences.preferences().api_config
