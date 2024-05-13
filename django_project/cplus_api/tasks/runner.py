"""Task to run scneario analysis."""

from celery import shared_task
import logging
import time
import json
from core.settings.utils import UUIDEncoder
from cplus_api.models.scenario import ScenarioTask

logger = logging.getLogger(__name__)


def create_scenario_task_runner(scenario_task: ScenarioTask):
    # below imports require PyQGIS to be initialised
    from cplus_api.utils.worker_analysis import (
        TaskConfig, WorkerScenarioAnalysisTask
    )

    task_config = TaskConfig.from_dict(scenario_task.detail)
    analysis_task = WorkerScenarioAnalysisTask(task_config, scenario_task)
    logger.info('Started prepare_run')
    analysis_task.prepare_run()
    logger.info('Finished prepare_run')
    logger.info(
        json.dumps(analysis_task.task_config.to_dict(), cls=UUIDEncoder))
    return analysis_task


@shared_task(name="run_scenario_analysis_task")
def run_scenario_analysis_task(scenario_task_id):  # pragma: no cover
    scenario_task = ScenarioTask.objects.get(id=scenario_task_id)
    scenario_task.task_on_started()
    logger.info(
        f'Triggered run_scenario_analysis_task {str(scenario_task.uuid)}')
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

    # set sieve mask path, snap layer path, and mask layers path
    from cplus.utils.conf import settings_manager, Settings
    settings_manager.set_value(
        Settings.SIEVE_MASK_PATH, analysis_task.task_config.sieve_mask_path
    )
    settings_manager.set_value(
        Settings.SNAP_LAYER, analysis_task.task_config.snap_layer
    )
    settings_manager.set_value(
        Settings.MASK_LAYERS_PATHS, '.'.join(
            analysis_task.task_config.mask_paths
        )
    )

    start_time = time.time()
    analysis_task.run()
    logger.info(f'execution time: {time.time() - start_time} seconds')
    # call finished() to upload layer outputs
    analysis_task.finished(True)
    # use qgs.exit() if worker can be reused to execute another task
    qgs.exit()
    # exitQgis causing worker lost
    # qgs.exitQgis()
