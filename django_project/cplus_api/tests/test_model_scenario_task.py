import mock
import uuid
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from core.models.base_task_request import TaskStatus
from core.models.task_log import TaskLog
from core.settings.utils import absolute_path
from cplus_api.tests.factories import ScenarioTaskF


class TestModelScenarioTask(TestCase):


    def setUp(self) -> None:
        self.scenario_task_ct = ContentType.objects.get(
            app_label="cplus_api", model="scenariotask")

    def check_log_exists(self, scenario_task, log):
        self.assertTrue(
            TaskLog.objects.filter(
                content_type=self.scenario_task_ct,
                object_id=scenario_task.pk,
                log__icontains=log
            ).exists()
        )

    def test_get_requester_name(self):
        scenario_task = ScenarioTaskF.create()
        user = scenario_task.submitted_by
        self.assertEqual(
            scenario_task.requester_name,
            f'{user.first_name} {user.last_name}'
        )
        user.last_name = ''
        user.save()
        self.assertEqual(
            scenario_task.requester_name,
            f'{user.first_name}'
        )
        user.first_name = ''
        user.last_name = 'Doe'
        user.save()
        self.assertEqual(
            scenario_task.requester_name,
            '-'
        )

    def test_add_log(self):
        scenario_task = ScenarioTaskF.create()
        scenario_task.add_log('test')
        self.check_log_exists(scenario_task, 'test')

    def test_task_on_sent(self):
        scenario_task = ScenarioTaskF.create()
        scenario_task.task_on_sent('task_id', 'task_name', '(1,)')
        scenario_task.refresh_from_db()
        self.assertEqual(scenario_task.task_id, 'task_id')
        self.assertEqual(scenario_task.task_name, 'task_name')
        self.assertEqual(scenario_task.parameters, '(1,)')

    def test_task_on_queued(self):
        scenario_task = ScenarioTaskF.create()
        scenario_task.task_on_queued('task_id', 'task_name', '(1,)')
        scenario_task.refresh_from_db()
        self.assertEqual(scenario_task.task_id, 'task_id')
        self.assertEqual(scenario_task.task_name, 'task_name')
        self.assertEqual(scenario_task.parameters, '(1,)')
        self.assertEqual(scenario_task.status, TaskStatus.QUEUED)

    def test_task_on_started(self):
        scenario_task = ScenarioTaskF.create()
        scenario_task.task_on_started()
        scenario_task.refresh_from_db()
        self.assertEqual(scenario_task.status, TaskStatus.RUNNING)
        self.assertFalse(scenario_task.errors)
        self.check_log_exists(scenario_task, 'Task has been started.')

    def test_task_on_completed(self):
        scenario_task = ScenarioTaskF.create()
        scenario_task.task_on_completed()
        scenario_task.refresh_from_db()
        self.assertEqual(scenario_task.status, TaskStatus.COMPLETED)
        self.check_log_exists(scenario_task, 'Task has been completed.')

    def test_task_on_cancelled(self):
        scenario_task = ScenarioTaskF.create()
        scenario_task.task_on_cancelled()
        scenario_task.refresh_from_db()
        self.assertEqual(scenario_task.status, TaskStatus.CANCELLED)
        self.check_log_exists(scenario_task, 'Task has been cancelled.')

    def test_task_on_errors(self):
        scenario_task = ScenarioTaskF.create()
        scenario_task.task_on_errors(Exception('test'))
        scenario_task.refresh_from_db()
        self.assertEqual(scenario_task.status, TaskStatus.STOPPED)
        self.assertEqual(scenario_task.errors, 'test\n')
        self.check_log_exists(scenario_task, 'Task is stopped with errors.')

    def test_task_on_retried(self):
        scenario_task = ScenarioTaskF.create()
        scenario_task.task_on_retried('Test')
        scenario_task.refresh_from_db()
        self.assertEqual(scenario_task.celery_retry, 1)
        self.assertEqual(scenario_task.celery_retry_reason, 'Test')
        self.check_log_exists(scenario_task, 'Task is retried by scheduler.')

    def test_is_possible_interrupted(self):
        scenario_task = ScenarioTaskF.create()
        self.assertFalse(scenario_task.is_possible_interrupted())
        scenario_task.status = TaskStatus.RUNNING
        scenario_task.save()
        self.assertFalse(scenario_task.is_possible_interrupted())
        scenario_task.last_update = timezone.now() - timedelta(days=1)
        scenario_task.save()
        self.assertTrue(scenario_task.is_possible_interrupted())

    def test_get_scenario_output_files(self):
        scenario_task = ScenarioTaskF.create()
        scenario_task.uuid = uuid.UUID('3e0c7dff-51f2-48c5-a316-15d9ca2407cb')
        results, total_files = (
            scenario_task.get_scenario_output_files('/home/web/test')
        )
        self.assertEqual(len(results), 0)
        self.assertEqual(total_files, 0)
        with mock.patch.object(scenario_task.submitted_by, 'id', 1):
            base_dir = absolute_path(
                'cplus_api', 'tests', 'samples'
            )
            results, total_files = (
                scenario_task.get_scenario_output_files(base_dir)
            )
            self.assertEqual(len(results), 2)
            self.assertEqual(total_files, 2)
            self.assertIn('final_output', results)
            self.assertIn('im3.json', results['final_output'][0])
            self.assertIn('implementation_models', results)
            self.assertIn('im1.json', results['implementation_models'][0])
