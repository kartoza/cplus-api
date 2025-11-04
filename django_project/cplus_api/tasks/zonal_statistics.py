import logging
import os
import time
import traceback

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from cplus_api.models.layer import InputLayer
from cplus_api.models.statistics import ZonalStatisticsTask
from cplus_api.utils.qgis_helper import qgis_application, create_bbox_vector_layer

logger = logging.getLogger(__name__)


@shared_task(name="calculate_zonal_statistics")
def calculate_zonal_statistics(zonal_task_id):
    """Celery worker for calculating zonal statistics of Naturebase layers."""
    try:
        zonal_task = ZonalStatisticsTask.objects.get(id=zonal_task_id)
    except ZonalStatisticsTask.DoesNotExist:
        logger.error("ZonalStatisticsTask not found: %s", zonal_task_id)
        return
    
    zonal_task.task_on_started()

    try:
        with qgis_application():
            from qgis.core import QgsRectangle, QgsRasterLayer, QgsVectorLayer
            from qgis.analysis import QgsZonalStatistics

            start_time = time.time()

            bbox = {
                'minx': zonal_task.bbox_minx,
                'miny': zonal_task.bbox_miny,
                'maxx': zonal_task.bbox_maxx,
                'maxy': zonal_task.bbox_maxy,
            }

            extent = QgsRectangle(bbox['minx'], bbox['miny'], bbox['maxx'], bbox['maxy'])

            nature_base_layers = InputLayer.objects.filter(source=InputLayer.LayerSources.NATURE_BASE)
            total = nature_base_layers.count()
            if total == 0:
                zonal_task.result = []
                zonal_task.save(update_fields=['result'])
                # Use base class func to update the other fields
                zonal_task.task_on_completed()
                return

            results = []
            attribute_prefix = "zs_"
            for idx, layer in enumerate(nature_base_layers):
                try:
                    if not layer.is_available():
                        logger.warning("Layer %s not available; skipping", layer.name)
                        results.append({'uuid': str(layer.uuid), 'layer_name': layer.name, 'mean_value': None})
                        continue

                    file_path = layer.download_to_working_directory(settings.TEMPORARY_LAYER_DIR)
                    if not file_path or not os.path.exists(file_path):
                        logger.warning("Download failed or file missing for layer %s", layer.name)
                        results.append({'uuid': str(layer.uuid), 'layer_name': layer.name, 'mean_value': None})
                        continue
                    
                    nature_base_raster = QgsRasterLayer(file_path, layer.name)
                    if not nature_base_raster.isValid():
                        logger.warning("Invalid raster for layer %s (%s)", layer.name, file_path)
                        results.append({'uuid': str(layer.uuid), 'layer_name': layer.name, 'mean_value': None})
                        continue

                    reference_layer = create_bbox_vector_layer(extent)
                    
                    zonal_stats = QgsZonalStatistics(
                        reference_layer, 
                        nature_base_raster, 
                        attribute_prefix, 
                        1,
                        QgsZonalStatistics.Statistic.Mean
                    )
                    zonal_stats.calculateStatistics(None)

                    feature = next(reference_layer.getFeatures())
                    mean_value = feature.attribute('_mean')

                    results.append(
                        {'uuid': str(layer.uuid), 
                         'layer_name': layer.name, 
                         'mean_value': float(mean_value) if mean_value is not None else None}
                    )
                except Exception as ex_layer:
                    logger.exception("Error processing zonal statistics for layer %s", layer.name)
                    results.append(
                        {'uuid': str(layer.uuid), 
                         'layer_name': layer.name, 
                         'mean_value': None}
                    )

                # Update progress
                progress = ((idx + 1) / total) * 100.0
                zonal_task.progress = progress
                zonal_task.last_update = timezone.now()
                zonal_task.save(update_fields=['progress', 'last_update'])

            zonal_task.result = results
            zonal_task.save(update_fields=['result'])
            zonal_task.task_on_completed()
            logger.info("Zonal stats finished in %s seconds", time.time() - start_time)

    except Exception as exc:
        # Capture error and logs
        tb = traceback.format_exc()
        logger.exception("Zonal stats task failed: %s", exc)
        zonal_task.error_message = str(exc)
        zonal_task.stack_trace_errors = tb
        zonal_task.task_on_errors(exception=exc, traceback=tb)
        zonal_task.save()
