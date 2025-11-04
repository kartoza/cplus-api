from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from core.models.base_task_request import BaseTaskRequest


class ZonalStatisticsTask(BaseTaskRequest):
    """Task db record for zonal statistics calculation."""

    # Bounding box should be in WGS84
    bbox_minx = models.FloatField()
    bbox_miny = models.FloatField()
    bbox_maxx = models.FloatField()
    bbox_maxy = models.FloatField()

    # List of {uuid, layer_name, mean_value} for each naturebase layer
    result = models.JSONField(null=True, blank=True)

    error_message = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = _("Zonal statistics task")
        verbose_name_plural = _("Zonal statistics tasks")
        ordering = ["-submitted_on"]

    def __str__(self):
        return f"ZonalStatisticsTask {self.uuid}"