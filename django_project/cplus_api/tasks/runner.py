"""Task to run scneario analysis."""

from celery import shared_task
import os
import logging
import time
import json
from django.utils import timezone
from cplus_api.models.scenario import ScenarioTask
from cplus_api.models.layer import BaseLayer, OutputLayer

logger = logging.getLogger(__name__)


def create_and_upload_output_layer(
        file_path: str, scenario_task: ScenarioTask,
        is_final_output: bool, group: str) -> OutputLayer:
    filename = os.path.basename(file_path)
    output_layer = OutputLayer.objects.create(
        name=filename,
        created_on=timezone.now(),
        owner=scenario_task.submitted_by,
        layer_type=BaseLayer.LayerTypes.RASTER,
        size=os.stat(file_path).st_size,
        is_final_output=is_final_output,
        scenario=scenario_task,
        group=group
    )
    with open(file_path, 'rb') as output_file:
        output_layer.file.save(filename, output_file)
    return output_layer


def create_scenario_task_runner(scenario_task: ScenarioTask):
    from cplus.tasks.analysis import ScenarioAnalysisTask
    from cplus.utils.conf import TaskConfig

    class WorkerScenarioAnalysisTask(ScenarioAnalysisTask):

        def __init__(self, task_config: TaskConfig,
                     scenario_task: ScenarioTask):
            super().__init__(
                task_config.scenario_name,
                task_config.scenario_desc,
                task_config.analysis_implementation_models,
                task_config.priority_layer_groups,
                task_config.analysis_extent,
                task_config.scenario
            )
            self.task_config = task_config
            self.scenario_task = scenario_task

        def prepare_run(self):
            # clear existing scenario directory if exists
            self.scenario_task.clear_resources()
            # create scenario directory for a user
            scenario_path = self.scenario_task.get_resources_path()
            os.makedirs(scenario_path)
            # clear existing output results
            OutputLayer.objects.filter(
                scenario=self.scenario_task
            ).delete()

        def get_settings_value(self, name: str,
                               default=None, setting_type=None):
            return self.task_config.get_value(name, default)

        def get_scenario_directory(self):
            return self.scenario_task.get_resources_path()

        def get_priority_layer(self, identifier):
            return self.task_config.get_priority_layer(identifier)

        def get_implementation_model(self, implementation_model_uuid):
            return self.task_config.get_implementation_model(
                implementation_model_uuid)

        def get_priority_layers(self):
            return self.task_config.get_priority_layers()

        def cancel_task(self, exception=None):
            # raise exception to stop the task
            if exception:
                raise exception
            else:
                raise Exception('Task stopped with errors!')

        def log_message(self, message: str, name: str = "qgis_cplus",
                        info: bool = True, notify: bool = True):
            self.scenario_task.add_log(
                message, logging.INFO if info else logging.ERROR)
            level = logging.INFO if info else logging.WARNING
            logger.log(level, message)

        def set_status_message(self, message):
            self.status_message = message
            self.scenario_task.progress_text = message
            self.scenario_task.save(update_fields=['progress_text'])

        def set_info_message(self, message, level):
            self.info_message = message
            self.scenario_task.progress_text = message
            self.scenario_task.save(update_fields=['progress_text'])

        def set_custom_progress(self, value):
            self.custom_progress = value
            self.scenario_task.progress = value
            self.scenario_task.save(update_fields=['progress'])

        def upload_scenario_outputs(self):
            scenario_output_files, total_files = (
                self.scenario_task.get_scenario_output_files()
            )
            status_msg = 'Uploading scenario outputs to storage.'
            self.set_status_message(status_msg)
            self.log_message(status_msg)
            self.log_message(json.dumps(scenario_output_files))
            self.set_custom_progress(0)
            total_uploaded_files = 0
            for group, files in scenario_output_files.items():
                is_final_output = group == 'final_output'
                if is_final_output:
                    create_and_upload_output_layer(
                        files[0], self.scenario_task, True, None)
                    total_uploaded_files += 1
                    self.set_custom_progress(
                        100 * (total_uploaded_files / total_files))
                else:
                    for file in files:
                        create_and_upload_output_layer(
                            file, self.scenario_task, False, group)
                        total_uploaded_files += 1
                        self.set_custom_progress(
                            100 * (total_uploaded_files / total_files))

        def finished(self, result: bool):
            if result:
                self.log_message("Finished from the main task \n")
                self.upload_scenario_outputs()
            else:
                self.log_message(
                    f"Error from task scenario task {self.error}", info=False)
            # clean directory
            self.scenario_task.clear_resources()

    task_config = TaskConfig.from_dict(scenario_task.detail)
    analysis_task = WorkerScenarioAnalysisTask(task_config, scenario_task)
    analysis_task.prepare_run()
    return analysis_task


@shared_task(name="run_scenario_analysis_task")
def run_scenario_analysis_task(scenario_task_id):
    scenario_task = ScenarioTask.objects.get(id=scenario_task_id)
    scenario_task.task_on_started()
    logger.info(
        f'Triggered run_scenario_analysis_task {str(scenario_task.uuid)}')
    start_time = time.time()
    from qgis.core import QgsApplication
    # Supply path to qgis install location
    QgsApplication.setPrefixPath("/usr/bin/qgis", True)
    # Create a reference to the QgsApplication.  Setting the
    # second argument to False disables the GUI.
    qgs = QgsApplication([], False)
    # Load providers
    qgs.initQgis()
    # init processing plugins
    import processing  # noqa
    from processing.core.Processing import Processing
    Processing.initialize()
    analysis_task = create_scenario_task_runner(scenario_task)
    analysis_task.run()
    logger.info(f'execution time: {time.time() - start_time} seconds')
    # call finished() to upload layer outputs
    analysis_task.finished(True)
    scenario_task.task_on_completed()
    # use qgs.exit() if worker can be reused to execute another task
    qgs.exit()
    # exitQgis causing worker lost
    # qgs.exitQgis()
