import mock
import uuid
from datetime import timedelta, datetime
from django.test import TestCase
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from core.models.base_task_request import TaskStatus
from core.models.task_log import TaskLog
from core.settings.utils import absolute_path
from cplus_api.tests.factories import ScenarioTaskF
from cplus_api.utils.celery_event_handlers import (
    find_scenario_task_by_args,
    task_sent_handler,
    task_received_handler,
    task_failure_handler,
    task_revoked_handler,
    task_internal_error_handler,
    task_retry_handler
)


class RequestObj(object):

    def __init__(self, id, name, task_args) -> None:
        self.id = id
        self.name = name
        self.args = task_args


class SenderObj(object):

    def __init__(self, name, request) -> None:
        self.name = name
        self.request = request


class TestModelScenarioTask(TestCase):
    def setUp(self) -> None:
        self.scenario_task_ct = ContentType.objects.get(
            app_label="cplus_api", model="scenariotask")

    def check_log_exists(self, scenario_task, log):
        task_log_qs = TaskLog.objects.filter(
            content_type=self.scenario_task_ct,
            object_id=scenario_task.pk,
            log__icontains=log
        )
        self.assertTrue(task_log_qs.exists())
        task_log = task_log_qs.first()
        self.assertEqual(str(task_log), log)

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
        self.assertEqual(str(scenario_task), str(scenario_task.uuid))

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
        self.check_log_exists(scenario_task, 'Task is sent to worker.')

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
        scenario_task.task_on_errors(Exception('test'), 'new-line')
        scenario_task.refresh_from_db()
        self.assertEqual(scenario_task.status, TaskStatus.STOPPED)
        self.assertEqual(scenario_task.stack_trace_errors, 'test\nnew-line\n')
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

    def test_find_scenario_task_by_args(self):
        scenario_task = ScenarioTaskF.create()
        find_task = find_scenario_task_by_args('test', [])
        self.assertFalse(find_task)
        find_task = find_scenario_task_by_args(
            'test', (scenario_task.id,))
        self.assertFalse(find_task)
        find_task = find_scenario_task_by_args(
            'run_scenario_analysis_task', (scenario_task.id,))
        self.assertEqual(find_task.id, scenario_task.id)

    def test_task_sent_handler(self):
        scenario_task = ScenarioTaskF.create()
        headers = {
            'task': 'test',
            'id': 'test-id'
        }
        task_args = (9999,)
        task_sent_handler(headers=headers, body=(task_args,))
        scenario_task.refresh_from_db()
        self.assertFalse(scenario_task.task_id)
        self.assertFalse(scenario_task.task_name)
        headers = {
            'task': 'run_scenario_analysis_task',
            'id': 'test-id'
        }
        task_args = (scenario_task.id,)
        task_sent_handler(headers=headers, body=(task_args,))
        scenario_task.refresh_from_db()
        self.assertEqual(scenario_task.task_id, 'test-id')
        self.assertEqual(
            scenario_task.task_name, 'run_scenario_analysis_task')

    def test_task_received_handler(self):
        scenario_task = ScenarioTaskF.create()
        request = RequestObj('test-id', 'run_scenario_analysis_task', (9999,))
        task_received_handler(None, request=request)
        scenario_task.refresh_from_db()
        self.assertFalse(scenario_task.task_id)
        self.assertFalse(scenario_task.task_name)
        request = RequestObj(
            'test-id', 'run_scenario_analysis_task', (scenario_task.id,))
        task_received_handler(None, request=request)
        scenario_task.refresh_from_db()
        self.assertEqual(scenario_task.task_id, 'test-id')
        self.assertEqual(scenario_task.task_name,
                         'run_scenario_analysis_task')
        self.assertEqual(scenario_task.parameters, f'({scenario_task.id},)')
        self.assertEqual(scenario_task.status, TaskStatus.QUEUED)

    def test_task_failure_handler(self):
        scenario_task = ScenarioTaskF.create()
        request = RequestObj('test-id', 'run_scenario_analysis_task', (9999,))
        task_failure_handler(
            request, args=request.args, exception=Exception('Errors'))
        scenario_task.refresh_from_db()
        self.assertNotEqual(scenario_task.status, TaskStatus.STOPPED)
        request = RequestObj(
            'test-id', 'run_scenario_analysis_task', (scenario_task.id,))
        task_failure_handler(
            request, args=request.args, exception=Exception('Errors'))
        scenario_task.refresh_from_db()
        self.assertEqual(scenario_task.status, TaskStatus.STOPPED)

    def test_task_revoked_handler(self):
        scenario_task = ScenarioTaskF.create(
            task_id='test-id'
        )
        request = RequestObj('test-id', 'test', (scenario_task.id,))
        sender = SenderObj(request.name, request)
        task_revoked_handler(sender, request=request)
        scenario_task.refresh_from_db()
        self.assertNotEqual(scenario_task.status, TaskStatus.CANCELLED)
        request = RequestObj(
            'test-id', 'run_scenario_analysis_task', (scenario_task.id,))
        sender = SenderObj(request.name, request)
        task_revoked_handler(sender, request=request)
        scenario_task.refresh_from_db()
        self.assertEqual(scenario_task.status, TaskStatus.CANCELLED)

    def test_task_internal_error_handler(self):
        scenario_task = ScenarioTaskF.create()
        request = RequestObj('test-id', 'run_scenario_analysis_task', (9999,))
        sender = SenderObj(request.name, request)
        task_internal_error_handler(
            sender, exception=Exception('Errors'))
        scenario_task.refresh_from_db()
        self.assertNotEqual(scenario_task.status, TaskStatus.STOPPED)
        request = RequestObj(
            'test-id', 'run_scenario_analysis_task', (scenario_task.id,))
        sender = SenderObj(request.name, request)
        task_internal_error_handler(
            sender, exception=Exception('Errors'))
        scenario_task.refresh_from_db()
        self.assertEqual(scenario_task.status, TaskStatus.STOPPED)

    def test_task_retry_handler(self):
        scenario_task = ScenarioTaskF.create()
        request = RequestObj('test-id', 'run_scenario_analysis_task', (9999,))
        sender = SenderObj(request.name, request)
        task_retry_handler(sender, 'test-retry')
        scenario_task.refresh_from_db()
        self.assertFalse(scenario_task.celery_retry)
        self.assertFalse(scenario_task.celery_retry_reason)
        request = RequestObj(
            'test-id', 'run_scenario_analysis_task', (scenario_task.id,))
        sender = SenderObj(request.name, request)
        task_retry_handler(sender, 'test-retry')
        scenario_task.refresh_from_db()
        self.assertEqual(scenario_task.celery_retry, 1)
        self.assertEqual(scenario_task.celery_retry_reason, 'test-retry')

    def test_get_detail_value(self):
        scenario_task = ScenarioTaskF.create()
        self.assertEqual(
            scenario_task.get_detail_value('scenario_name'), 'Scenario 1')
        self.assertEqual(
            scenario_task.get_detail_value('invalid', ''), '')

    def test_get_processing_time(self):
        scenario_task = ScenarioTaskF.create()
        self.assertEqual(scenario_task.get_processing_time(), '')
        scenario_task.started_at = datetime(2023, 8, 14, 8, 8, 8)
        scenario_task.finished_at = datetime(2023, 8, 14, 8, 8, 10)
        self.assertEqual(
            scenario_task.get_processing_time(),
            '00:00:02.00'
        )
