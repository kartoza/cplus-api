"""Task to run scneario analysis."""

from celery import shared_task
import os
import logging
import time
import shutil
from cplus_api.models.scenario import ScenarioTask

logger = logging.getLogger(__name__)


def run_scenario_task(scenario_task: ScenarioTask):
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

        def get_settings_value(self, name: str,
                               default=None, setting_type=None):
            return self.task_config.get_value(name, default)

        def get_scenario_directory(self):
            base_dir = '/home/web/media'
            scenario_path = os.path.join(
                f"{base_dir}",
                f"{str(self.scenario_task.submitted_by.id)}",
                f'{str(self.scenario_task.uuid)}',
            )
            if os.path.exists(scenario_path):
                shutil.rmtree(scenario_path)
            os.makedirs(scenario_path)
            return scenario_path

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

    task_config = TaskConfig.from_dict(scenario_task.detail)
    analysis_task = WorkerScenarioAnalysisTask(task_config, scenario_task)
    analysis_task.run()


@shared_task(name="run_scenario_analysis_task")
def run_scenario_analysis_task(scenario_task_id):
    scenario_task = ScenarioTask.objects.get(id=scenario_task_id)
    scenario_task.task_on_started()
    logger.info('Triggered run_scenario_analysis_task')
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
    print("Success!")
    run_scenario_task(scenario_task)
    print(f'execution time: {time.time() - start_time} seconds')
    # use qgs.exit() if worker can be reused to execute another task
    # qgs.exit()
    qgs.exitQgis()
    scenario_task.task_on_completed()
