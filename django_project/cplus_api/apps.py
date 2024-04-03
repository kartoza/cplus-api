from django.apps import AppConfig


class CplusApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cplus_api'

    def ready(self):
        from cplus_api.utils.celery_event_handlers import (
            task_sent_handler
        )
        pass

