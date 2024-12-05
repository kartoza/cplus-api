import logging
from celery import shared_task
from cplus_api.models import (
    InputLayer
)


logger = logging.getLogger(__name__)


@shared_task(name="move_input_layer_file")
def move_input_layer_file(layer_uuid):
    """
    Move input layer file after updating component type or privacy type
    """
    layer = InputLayer.objects.get(uuid=layer_uuid)
    layer.move_file_location()
    if layer.is_available():
        logger.info(
            f'Layer {layer.uuid} is stored in {layer.file.name} '
            f'with size {layer.size}'
        )
    else:
        logger.warn(f'Layer {layer.uuid} is not available!')
