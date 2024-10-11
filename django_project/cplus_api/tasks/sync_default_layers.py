import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="sync_default_layers")
def sync_default_layers():
    """
    Create Input Layers from default layers copied to S3/local directory
    """
    from cplus_api.utils.layers import (
        delete_invalid_default_layers,
        sync_cplus_layers
    )

    delete_invalid_default_layers()
    sync_cplus_layers()
