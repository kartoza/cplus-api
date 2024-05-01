"""Task to remove resources."""

import logging

from celery import shared_task
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from core.models.base_task_request import TaskStatus
from core.models.preferences import SitePreferences
from core.models.task_log import TaskLog
from cplus_api.models.scenario import ScenarioTask

logger = logging.getLogger(__name__)


@shared_task(name="check_scenario_task")
def check_scenario_task():
    """
    Check running Scenario Task and mark them as 'Stopped with error'
    if they don't have new log after certain threshold.

    Running task without new log after certain threshold could indicate
    they were stopped/interrupted halfway.
    """
    elapsed_time_threshold = (
        SitePreferences.preferences().task_runtime_threshold
    )

    running_scenarios = ScenarioTask.objects.filter(status=TaskStatus.RUNNING)
    for scenario in running_scenarios:
        # we check whether the last logs have passed the threshold,
        # instead of comparing to scenario's start time.
        try:
            last_log = TaskLog.objects.filter(
                object_id=scenario.id,
                content_type=ContentType.objects.get_for_model(scenario).id
            ).latest('date_time')
            elapsed_seconds = (
                    timezone.now() - last_log.date_time
            ).total_seconds()
        except TaskLog.DoesNotExist:
            elapsed_seconds = (
                    timezone.now() - scenario.started_at
            ).total_seconds()

        # if elapsed seconds is more than threshold in seconds
        if elapsed_seconds > (elapsed_time_threshold * 60):
            scenario.task_on_errors()
