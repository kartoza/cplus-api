"""QGIS initialization utils for Celery tasks."""

from contextlib import contextmanager
import logging
import os
import uuid

logger = logging.getLogger(__name__)


@contextmanager
def qgis_application():
    """
    Context manager for QGIS application initialization and cleanup.

    Usage:
        with qgis_application():
            from qgis.core import QgsVectorLayer


    In the long term, we might consider having a running instance
    of QGIS Server and incorporate custom server plugins that
    incorporate CPLUS functionality.
    """
    from qgis.core import QgsApplication

    QgsApplication.setPrefixPath("/usr/bin/qgis", True)

    qgs = QgsApplication([], False)
    qgs.initQgis()

    logger.info("QGIS application initialized")

    try:
        yield qgs
    finally:
        qgs.exit()
        logger.info("QGIS application cleaned up")


def create_bbox_vector_layer(extent):
    """
    Create a temporary vector layer from a bounding box extent.

    Note: This function must be called within a qgis_application() context.

    :returns: A QGIS vector layer with a single polygon feature.
    :rtype: QgsVectorLayer
    """
    from qgis.core import QgsVectorLayer, QgsFeature, QgsGeometry, QgsPointXY

    # Create a memory vector layer
    vector_layer = QgsVectorLayer(
        "Polygon?crs=EPSG:4326", "bbox_layer", "memory"
    )

    provider = vector_layer.dataProvider()

    feature = QgsFeature()
    points = [
        QgsPointXY(extent.xMinimum(), extent.yMinimum()),
        QgsPointXY(extent.xMaximum(), extent.yMinimum()),
        QgsPointXY(extent.xMaximum(), extent.yMaximum()),
        QgsPointXY(extent.xMinimum(), extent.yMaximum()),
        QgsPointXY(extent.xMinimum(), extent.yMinimum()),
    ]
    geometry = QgsGeometry.fromPolygonXY([points])
    feature.setGeometry(geometry)

    provider.addFeatures([feature])
    vector_layer.updateExtents()

    return vector_layer


_processing_ready = False


def _configure_processing():
    """Initialize QGIS Processing providers once."""
    global _processing_ready
    if _processing_ready:
        return

    from qgis.core import QgsApplication
    try:
        import processing  # noqa: F401
        from qgis.analysis import QgsNativeAlgorithms
        QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())
        # Sdd GDAL provider 
        try:
            from processing.algs.gdal.GdalAlgorithmProvider import (
                GdalAlgorithmProvider,
            )
            QgsApplication.processingRegistry().addProvider(
                GdalAlgorithmProvider()
            )
        except Exception:
            # If GDAL is already available, this is fine
            pass
        _processing_ready = True
        logger.info("QGIS Processing initialized")
    except Exception as exc:
        logger.exception("Failed to initialize QGIS Processing: %s", exc)
        raise


def clip_raster_by_bbox_qgis(input_path: str, bbox, temp_dir: str) -> str:
    """
    Clip a raster using QGIS Processing - GDAL: cliprasterbyextent.

    Note: This function must be called within a qgis_application() 
    context.

    :param input_path: path to input raster which should be in 
    EPSG:4326.
    :type input_path: str

    :param bbox: minx, miny, maxx, maxy in EPSG:4326
    :type bbox: iterable (tuple/list)

    :param temp_dir: directory for output.
    :type temp_dir: str

    :returns: Path to the output clipped GeoTIFF.
    :rtype: str
    """
    from qgis.core import QgsRectangle
    import processing

    _configure_processing()

    minx, miny, maxx, maxy = bbox
    extent = QgsRectangle(minx, miny, maxx, maxy)

    # Use QgsRectangle to normalize the extents. 
    projwin = f"{extent.xMinimum()},{extent.yMaximum()},{extent.xMaximum()},{extent.yMinimum()}"

    out_path = os.path.join(temp_dir, f"{uuid.uuid4().hex}.tif")

    params = {
        "INPUT": input_path,
        "PROJWIN": projwin,
        "NODATA": None,
        "OPTIONS": "",
        "DATA_TYPE": 0,  # use input data type
        "EXTRA": "",
        "OUTPUT": out_path,
    }
    processing.run("gdal:cliprasterbyextent", params)

    return out_path
