from django.db import models
import uuid
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.utils import timezone
import logging
from core.models.task_log import TaskLog


class TaskStatus(models.TextChoices):
    PENDING = 'Pending', _('Pending')
    QUEUED = 'Queued', _('Queued')
    RUNNING = 'Running', _('Running')
    STOPPED = 'Stopped', _('Stopped with error')
    COMPLETED = 'Completed', _('Completed')
    CANCELLED = 'Cancelled', _('Cancelled')
    INVALIDATED = 'Invalidated', _('Invalidated')


COMPLETED_STATUS = [
    TaskStatus.COMPLETED, TaskStatus.STOPPED, TaskStatus.CANCELLED
]
READ_ONLY_STATUS = [
    TaskStatus.COMPLETED, TaskStatus.STOPPED, TaskStatus.RUNNING,
    TaskStatus.CANCELLED
]


class BaseTaskRequest(models.Model):

    status = models.CharField(
        max_length=255,
        choices=TaskStatus.choices,
        default=TaskStatus.PENDING
    )

    task_name = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    task_id = models.CharField(
        max_length=256,
        null=True,
        blank=True
    )

    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True
    )

    submitted_on = models.DateTimeField()

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True
    )

    finished_at = models.DateTimeField(
        null=True,
        blank=True
    )

    errors = models.TextField(
        null=True,
        blank=True
    )

    progress = models.FloatField(
        null=True,
        blank=True
    )

    progress_text = models.TextField(
        null=True,
        blank=True
    )

    last_update = models.DateTimeField(
        null=True,
        blank=True
    )

    celery_retry = models.IntegerField(
        default=0
    )

    celery_last_retry_at = models.DateTimeField(
        null=True,
        blank=True
    )

    celery_retry_reason = models.TextField(
        null=True,
        blank=True
    )

    parameters = models.TextField(
        null=True,
        blank=True
    )

    class Meta:
        """Meta class for abstract base task request."""
        abstract = True

    def __str__(self):
        return str(self.uuid)

    @property
    def requester_name(self):
        if self.submitted_by and self.submitted_by.first_name:
            name = self.submitted_by.first_name
            if self.submitted_by.last_name:
                name = f'{name} {self.submitted_by.last_name}'
            return name
        return '-'

    def add_log(self, log, level=logging.INFO):
        task_log = TaskLog(
            content_object=self,
            log=log,
            level=level,
            date_time=timezone.now()
        )
        task_log.save()

    def task_on_sent(self, task_id, task_name, parameters):
        self.task_id = task_id
        self.task_name = task_name
        self.parameters = parameters
        self.last_update = timezone.now()
        self.save(
            update_fields=['task_id', 'task_name',
                           'parameters', 'last_update']
        )

    def task_on_queued(self, task_name, task_id, parameters):
        """
        This event is called when task is placed on worker's queued.

        This event may be skipped when the worker's queue is empty.
        """
        if self.task_id == '':
            self.task_id = task_id
            self.task_name = task_name
            self.parameters = parameters
        self.last_update = timezone.now()
        self.status = TaskStatus.QUEUED
        self.save(
            update_fields=['task_id', 'task_name',
                           'parameters', 'last_update', 'status']
        )

    def task_on_started(self):
        """Initialize fields when task is started."""
        self.status = TaskStatus.RUNNING
        self.started_at = timezone.now()
        self.finished_at = None
        self.progress = 0
        self.progress_text = None
        self.last_update = timezone.now()
        self.save()

    def task_on_completed(self):
        self.last_update = timezone.now()
        self.status = TaskStatus.COMPLETED
        self.add_log('Task has been completed.')
        self.finished_at = timezone.now()
        self.save(
            update_fields=['last_update', 'status', 'finished_at']
        )

    def task_on_cancelled(self):
        self.last_update = timezone.now()
        self.status = TaskStatus.CANCELLED
        self.add_log('Task has been cancelled.')
        self.save(
            update_fields=['last_update', 'status']
        )

    def task_on_errors(self, exception=None):
        self.last_update = timezone.now()
        self.status = TaskStatus.STOPPED
        self.errors = str(exception)
        self.add_log('Task is stopped with errors.', logging.ERROR)
        self.add_log(str(exception), logging.ERROR)
        self.save(
            update_fields=['last_update', 'status', 'errors']
        )

    def task_on_retried(self, reason):
        self.last_update = timezone.now()
        self.celery_retry += 1
        self.celery_last_retry_at = timezone.now()
        self.celery_retry_reason = str(reason)
        self.add_log('Task is retried by scheduler.')
        self.save(
            update_fields=['last_update', 'celery_retry',
                           'celery_last_retry_at', 'celery_retry_reason']
        )

    def is_possible_interrupted(self, delta = 1800):
        if (
            self.status == TaskStatus.QUEUED or
            self.status == TaskStatus.RUNNING
        ):
            # check if last_update is more than 30mins than current date time
            if self.last_update:
                diff_seconds = timezone.now() - self.last_update
                return diff_seconds.total_seconds() >= delta
        return False
