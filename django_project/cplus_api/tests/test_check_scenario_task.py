from datetime import timedelta
from unittest import mock

from django.utils import timezone

from core.models.base_task_request import TaskStatus
from cplus_api.tasks.check_scenario_task import check_scenario_task
from cplus_api.tests.common import BaseAPIViewTransactionTest
from cplus_api.tests.factories import (
    ScenarioTaskF
)


@mock.patch('core.models.base_task_request.timezone')
class TestCheckScenarioTask(BaseAPIViewTransactionTest):
    """
    Test checking scenario task if they have run for too long.
    """

    def test_non_running_task_not_checked(self, mock_tz):
        """
        Test that only running tasks are checked.
        In this case, the running task's last log was added 150 minutes ago,
        which is more than the threshold (120 minutes), so it will be
        marked as 'Stopped with errors'
        """
        mock_tz.now.return_value = timezone.now() - timedelta(minutes=150)
        task_running = ScenarioTaskF.create(
            status=TaskStatus.RUNNING
        )
        task_running.add_log('Test Log')
        non_running_tasks = []
        non_running_statuses = [
            TaskStatus.PENDING,
            TaskStatus.QUEUED,
            TaskStatus.COMPLETED,
            TaskStatus.CANCELLED,
            TaskStatus.INVALIDATED
        ]
        for status in non_running_statuses:
            task = ScenarioTaskF.create(
                status=status
            )
            task.add_log('Test Log')
            non_running_tasks.append(task)

        check_scenario_task()

        task_running.refresh_from_db()
        self.assertEquals(task_running.status, TaskStatus.STOPPED)

        for task in non_running_tasks:
            task.refresh_from_db()
            self.assertNotEquals(task.status, TaskStatus.STOPPED)

    def test_running_task_without_log(self, mock_tz):
        """
        Running task without log will have its started_at checked
        to be compared against threshold
        """
        mock_tz.now.return_value = timezone.now() - timedelta(minutes=150)
        task_running = ScenarioTaskF.create(
            status=TaskStatus.RUNNING,
            started_at=timezone.now() - timedelta(minutes=150)
        )
        check_scenario_task()
        task_running.refresh_from_db()
        self.assertEquals(task_running.status, TaskStatus.STOPPED)

    def test_running_task_without_log_started_at(self, mock_tz):
        """
        Running task without log and started_at will have its
        submitted_on checked to be compared against threshold
        """
        mock_tz.now.return_value = timezone.now() - timedelta(minutes=150)
        task_running = ScenarioTaskF.create(
            status=TaskStatus.RUNNING,
            submitted_on=timezone.now() - timedelta(minutes=150)
        )
        check_scenario_task()
        task_running.refresh_from_db()
        self.assertEquals(task_running.status, TaskStatus.STOPPED)
