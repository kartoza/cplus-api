import os
import shutil
from django.db import models
from django.contrib.contenttypes.models import ContentType
from core.models.base_task_request import BaseTaskRequest
from core.models.task_log import TaskLog


DEFAULT_BASE_DIR = '/home/web/media'
EXCLUDED_OUTPUT_DIR_NAMES = [
    'ncs_carbon', 'ncs_pathway', 'priority_layer',
    'ncs_carbons', 'ncs_pathways', 'priority_layers'
]


class ScenarioTask(BaseTaskRequest):

    api_version = models.CharField(
        max_length=256
    )

    plugin_version = models.CharField(
        max_length=256
    )

    detail = models.JSONField(
        default=dict
    )

    def task_on_started(self):
        super().task_on_started()
        # clean logs
        ct = ContentType.objects.get(
            app_label="cplus_api", model="scenariotask")
        TaskLog.objects.filter(
            content_type=ct,
            object_id=self.pk
        ).delete()
        self.add_log('Task has been started.')

    def task_on_cancelled(self):
        super().task_on_cancelled()
        # clean resources
        self.clear_resources()

    def task_on_errors(self, exception=None, traceback=None):
        super().task_on_errors(exception, traceback)
        # clean resources
        self.clear_resources()

    def get_resources_path(self, base_dir=DEFAULT_BASE_DIR):
        return os.path.join(
            f"{base_dir}",
            f"{str(self.submitted_by.id)}",
            f'{str(self.uuid)}',
        )

    def clear_resources(self, base_dir=DEFAULT_BASE_DIR):
        resources_path = self.get_resources_path(base_dir)
        if os.path.exists(resources_path):
            shutil.rmtree(resources_path)

    def get_scenario_output_files(self, base_dir=DEFAULT_BASE_DIR):
        directory_path = self.get_resources_path(base_dir)
        results = {}
        total_files = 0
        if not os.path.exists(directory_path):
            return results, total_files
        for path, dirs, files in os.walk(directory_path):
            for file in files:
                if file.endswith('.xml'):
                    continue
                fp = os.path.join(path, file)
                parent_dir = os.path.dirname(fp)
                parent_dir_name = os.path.basename(parent_dir)
                if parent_dir_name in EXCLUDED_OUTPUT_DIR_NAMES:
                    continue
                if parent_dir_name == str(self.uuid):
                    results['final_output'] = [fp]
                elif parent_dir_name in results:
                    results[parent_dir_name].append(fp)
                else:
                    results[parent_dir_name] = [fp]
                total_files += 1
        return results, total_files
