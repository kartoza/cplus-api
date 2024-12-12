from celery import shared_task
from django.utils import timezone


@shared_task(name="sync_default_layers")
def sync_default_layers():
    """
    Create Input Layers from default layers copied to S3/local directory
    """
    from cplus_api.utils.layers import (
        delete_invalid_default_layers,
        sync_nature_base,
        sync_cplus_layers
    )

    delete_invalid_default_layers()
    sync_nature_base()
    sync_cplus_layers()

