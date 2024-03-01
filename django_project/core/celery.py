from __future__ import absolute_import, unicode_literals

import os
import logging
from celery import Celery, signals
from celery.utils.serialization import strtobool
from celery.worker.control import inspect_command


logger = logging.getLogger(__name__)
EXCLUDED_TASK_LIST = []

# set the default Django settings module for the 'celery' program.
# this is also used in manage.py
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# Get the base REDIS URL, default to redis' default
BASE_REDIS_URL = (
    f'redis://default:{os.environ.get("REDIS_PASSWORD", "")}'
    f'@{os.environ.get("REDIS_HOST", "")}',
)

app = Celery('ciplus-api')

# Using a string here means the worker don't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')
# set visibility timeout (Redis) to 3 hours
# https://stackoverflow.com/questions/27310899/
# celery-is-rerunning-long-running-completed-tasks-over-and-over
app.conf.broker_transport_options = {'visibility_timeout': 3 * 3600}

# ------------------------------------
# Task event handlers
# ------------------------------------

@signals.after_task_publish.connect
def task_sent_handler(sender=None, headers=None, body=None, **kwargs):
    # task is sent to celery, but might not be queued to worker yet
    info = headers if 'task' in headers else body
    task_id = info['id']
    task_args = info['argsrepr'] if 'argsrepr' in info else ''
    if info['task'] in EXCLUDED_TASK_LIST:
        return


@signals.task_received.connect
def task_received_handler(sender, request=None, **kwargs):
    # task should be queued
    task_id = request.id if request else None
    task_args = request.args
    task_name = request.name if request else ''
    if task_name in EXCLUDED_TASK_LIST:
        return


@signals.task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None,
                        args=None, **kwargs):
    # task is running
    task_name = sender.name if sender else ''
    if task_name in EXCLUDED_TASK_LIST:
        return


@signals.task_success.connect
def task_success_handler(sender, **kwargs):
    task_name = sender.name if sender else ''
    if task_name in EXCLUDED_TASK_LIST:
        return
    task_id = sender.request.id


@signals.task_failure.connect
def task_failure_handler(sender, task_id=None, args=None,
                         exception=None, **kwargs):
    task_name = sender.name if sender else ''
    if task_name in EXCLUDED_TASK_LIST:
        return


@signals.task_revoked.connect
def task_revoked_handler(sender, request = None, **kwargs):
    task_name = sender.name if sender else ''
    if task_name in EXCLUDED_TASK_LIST:
        return
    task_id = request.id if request else None


@signals.task_internal_error.connect
def task_internal_error_handler(sender, task_id=None,
                                exception=None, **kwargs):
    task_name = sender.name if sender else ''
    if task_name in EXCLUDED_TASK_LIST:
        return


@signals.task_retry.connect
def task_retry_handler(sender, reason, **kwargs):
    task_name = sender.name if sender else ''
    if task_name in EXCLUDED_TASK_LIST:
        return
    task_id = sender.request.id
    logger.info(f'on task_retry_handler {task_id}')


# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

app.conf.broker_url = BASE_REDIS_URL

# this allows you to schedule items in the Django admin.
app.conf.beat_scheduler = 'django_celery_beat.schedulers.DatabaseScheduler'

# Task cron job schedules
# app.conf.beat_schedule = {
#     'task-id': {
#         'task': 'task_path',
#         'schedule': crontab(minute='*/5'),  # Run every 5 minute
#     },
# }

@inspect_command(
    alias='dump_conf',
    signature='[include_defaults=False]',
    args=[('with_defaults', strtobool)],
)
def conf(state, with_defaults=False, **kwargs):
    """
    This overrides the `conf` inspect command to effectively disable it.
    This is to stop sensitive configuration info appearing in e.g. Flower.
    (Celery makes an attempt to remove sensitive info,but it is not foolproof)
    """
    return {'error': 'Config inspection has been disabled.'}
