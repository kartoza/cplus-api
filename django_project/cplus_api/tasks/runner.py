"""Task to run scneario analysis."""

from celery import shared_task
import logging
import time
import json
from cplus_api.models.scenario import ScenarioTask

logger = logging.getLogger(__name__)


def run_dummy_task(scenario_task: ScenarioTask):
    from cplus.tasks.analysis import ScenarioAnalysisTask
    from cplus.utils.conf import TaskConfig
    task_config = TaskConfig.from_dict(scenario_task.detail)
    analysis_task = ScenarioAnalysisTask(task_config)
    analysis_task.run()


@shared_task(name="run_scenario_analysis_task")
def run_scenario_analysis_task(scenario_task_id):
    scenario_task = ScenarioTask.objects.get(id=scenario_task_id)
    scenario_task.task_on_started()
    logger.info('Triggered run_scenario_analysis_task')
    raise Exception('Test error!!')
    return
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
    run_dummy_task(scenario_task)
    print(f'execution time: {time.time() - start_time} seconds')
    # use qgs.exit() if worker can be reused to execute another task
    # qgs.exit()
    qgs.exitQgis()
    scenario_task.task_on_completed()
