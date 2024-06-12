import logging
from celery import shared_task
from cplus_api.models import (
    InputLayer
)


logger = logging.getLogger(__name__)


@shared_task(name="verify_input_layer")
def verify_input_layer(layer_id):
    """
    Verify input layer: directory + size.
    """
    layer = InputLayer.objects.get(id=layer_id)
    layer.fix_layer_metadata()
    if layer.is_available():
        logger.info(
            f'Layer {layer.uuid} is stored in {layer.file.name} '
            f'with size {layer.size}'
        )
    else:
        logger.warn(f'Layer {layer.uuid} is not available!')
