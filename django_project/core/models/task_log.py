from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class TaskLog(models.Model):
    log = models.TextField()
    level = models.IntegerField()
    date_time = models.DateTimeField()
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    def __str__(self):
        return self.log

    class Meta:
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]
