from __future__ import absolute_import, unicode_literals

import os
import logging
import sys
from celery import Celery, signals
from celery.utils.serialization import strtobool
from celery.worker.control import inspect_command
from celery.result import AsyncResult
from celery.schedules import crontab


logger = logging.getLogger(__name__)

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

# use max task = 1 to avoid memory leak from qgis processing tools
app.conf.worker_max_tasks_per_child = 1

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

app.conf.broker_url = BASE_REDIS_URL

# this allows you to schedule items in the Django admin.
app.conf.beat_scheduler = 'django_celery_beat.schedulers.DatabaseScheduler'

# Task cron job schedules
app.conf.beat_schedule = {
    'remove-layers': {
        # Use name from @shared_task(name="remove_layers")
        'task': 'remove_layers',
        'schedule': crontab(minute='0', hour='1'),  # Run everyday at 1am
    },
    'check-scenario-task': {
        'task': 'check_scenario_task',
        'schedule': crontab(hour='*'),  # Run every hour
    },
    'clean-multipart-upload': {
        'task': 'clean_multipart_upload',
        'schedule': crontab(minute='0', hour='2'),  # Run everyday at 2am
    }
}


@signals.worker_before_create_process.connect
def worker_create_process_handler(**kwargs):
    logger.info('******worker_before_create_process******')


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


def cancel_task(task_id: str):
    """
    Cancel task if it's ongoing.

    :param task_id: task identifier
    """
    try:
        res = AsyncResult(task_id)
        if not res.ready():
            # find if there is running task and stop it
            app.control.revoke(
                task_id,
                terminate=True,
                signal='SIGKILL'
            )
    except Exception as ex:
        logger.error(f'Failed cancel_task: {task_id}')
        logger.error(ex)


is_worker = os.environ.get('CPLUS_WORKER', 0)
if is_worker:
    # init qgis
    sys.path.insert(0, '/usr/share/qgis/python/plugins')
    sys.path.insert(0, '/usr/share/qgis/python')
    sys.path.append('/usr/lib/python3/dist-packages')
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from qgis.core import *  # noqa
    QgsApplication.setPrefixPath("/usr/bin/qgis", True)
    logger.info('*******QGIS INIT DONE*********')
