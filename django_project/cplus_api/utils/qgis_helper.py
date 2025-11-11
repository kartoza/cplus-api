"""QGIS initialization utils for Celery tasks."""

import logging
from contextlib import contextmanager

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
