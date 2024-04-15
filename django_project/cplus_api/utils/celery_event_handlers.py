import logging
from celery import signals
from cplus_api.models.scenario import ScenarioTask


logger = logging.getLogger(__name__)


# ------------------------------------
# Task event handlers
# ------------------------------------
KNOWN_TASK_LIST = ['run_scenario_analysis_task']


def find_scenario_task_by_args(task_name, task_args) -> ScenarioTask:
    if task_name not in KNOWN_TASK_LIST:
        return None
    if len(task_args) == 0:
        return None
    return ScenarioTask.objects.filter(
        id=task_args[0]
    ).first()


@signals.after_task_publish.connect
def task_sent_handler(sender=None, headers=None, body=None, **kwargs):
    # task is sent to celery, but might not be queued to worker yet
    info = headers if 'task' in headers else body
    task_id = info['id']
    task_name = info['task']
    task_args = body[0]
    scenario_task = find_scenario_task_by_args(task_name, task_args)
    if scenario_task is None:
        return
    scenario_task.task_on_sent(
        task_id, info['task'], str(task_args)
    )


@signals.task_received.connect
def task_received_handler(sender, request=None, **kwargs):
    # task should be queued
    task_id = request.id if request else None
    task_args = request.args
    task_name = request.name if request else ''
    scenario_task = find_scenario_task_by_args(task_name, task_args)
    if scenario_task is None:
        return
    scenario_task.task_on_queued(
        task_id, task_name, str(task_args)
    )


@signals.task_failure.connect
def task_failure_handler(sender, task_id=None, args=None,
                         exception=None, traceback=None, **kwargs):
    task_name = sender.name if sender else ''
    scenario_task = find_scenario_task_by_args(task_name, args)
    if scenario_task is None:
        return
    scenario_task.task_on_errors(exception, traceback)


@signals.task_revoked.connect
def task_revoked_handler(sender, request = None, **kwargs):
    task_name = sender.name if sender else ''
    task_id = request.id if request else None
    task_args = request.args if request else []
    scenario_task = find_scenario_task_by_args(task_name, task_args)
    if scenario_task is None:
        return
    if scenario_task.task_id == task_id:
        scenario_task.task_on_cancelled()


@signals.task_internal_error.connect
def task_internal_error_handler(sender, task_id=None,
                                exception=None, **kwargs):
    task_name = sender.name if sender else ''
    task_args = sender.request.args
    scenario_task = find_scenario_task_by_args(task_name, task_args)
    if scenario_task is None:
        return
    scenario_task.task_on_errors(exception)


@signals.task_retry.connect
def task_retry_handler(sender, reason, **kwargs):
    task_name = sender.name if sender else ''
    task_args = sender.request.args
    scenario_task = find_scenario_task_by_args(task_name, task_args)
    if scenario_task is None:
        return
    task_id = sender.request.id
    logger.info(f'on task_retry_handler {task_id}')
    scenario_task.task_on_retried(str(reason))
