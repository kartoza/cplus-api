from django.db import models
from core.models.base_task_request import BaseTaskRequest


class ScenarioTask(BaseTaskRequest):

    api_version = models.CharField(
        max_length=256
    )

    plugin_version = models.CharField(
        max_length=256
    )

    detail = models.JSONField(
        default=dict
    )
