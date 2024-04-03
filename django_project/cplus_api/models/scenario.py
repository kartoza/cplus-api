from django.db import models
from django.contrib.contenttypes.models import ContentType
from core.models.base_task_request import BaseTaskRequest
from core.models.task_log import TaskLog


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

    def task_on_started(self):
        super().task_on_started()
        # clean logs
        ct = ContentType.objects.get(
            app_label="cplus_api", model="scenariotask")
        TaskLog.objects.filter(
            content_type=ct,
            object_id=self.pk
        ).delete()
