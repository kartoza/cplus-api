"""Task to run scneario analysis."""

from celery import shared_task
import logging
import time
import json
from django.conf import settings
from core.settings.utils import UUIDEncoder
from cplus_api.models.scenario import ScenarioTask

logger = logging.getLogger(__name__)


def create_scenario_task_runner(scenario_task: ScenarioTask):
    """Create and prepare worker task.

    :param scenario_task: scenario task object
    :type scenario_task: ScenarioTask
    :return: worker task that is ready to be run
    :rtype: WorkerScenarioAnalysisTask
    """
    # below imports require PyQGIS to be initialised
    from cplus_api.utils.worker_analysis import (
        APITaskConfig, WorkerScenarioAnalysisTask
    )

    task_config = APITaskConfig.from_dict(scenario_task.detail)
    analysis_task = WorkerScenarioAnalysisTask(task_config, scenario_task)
    logger.info('Started prepare_run')
    analysis_task.prepare_run()
    logger.info('Finished prepare_run')
    logger.info(
        json.dumps(analysis_task.task_config.to_dict(), cls=UUIDEncoder))
    return analysis_task


@shared_task(name="run_scenario_analysis_task")
def run_scenario_analysis_task(scenario_task_id):
    """Run the scenario analysis.

    :param scenario_task_id: scenario task object id
    :type scenario_task_id: int
    """
    # Fetch ScenarioTask Object
    scenario_task = ScenarioTask.objects.get(id=scenario_task_id)
    scenario_task.task_on_started()
    scenario_task.code_version = (
        f"{settings.CODE_RELEASE_VERSION}-{settings.CODE_COMMIT_HASH}"
    )
    scenario_task.save(update_fields=['code_version'])
    logger.info(
        f'Triggered run_scenario_analysis_task {str(scenario_task.uuid)}')

    # initialize QGIS
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

    # Run scenario task
    analysis_task = create_scenario_task_runner(scenario_task)
    start_time = time.time()
    analysis_task.run()
    logger.info(f'execution time: {time.time() - start_time} seconds')

    # call finished() to upload layer outputs
    analysis_task.finished(True)

    # use qgs.exit() if worker can be reused to execute another task
    qgs.exit()
    # NOTE: exitQgis causing worker lost
    # qgs.exitQgis()
