"""Task to run scneario analysis."""

from celery import shared_task
import logging
import time
import json

logger = logging.getLogger(__name__)


def run_dummy_task():
    from cplus.tasks.analysis import ScenarioAnalysisTask
    from cplus.utils.conf import TaskConfig
    with open('/home/web/media/input.json', 'r') as fp:
        task_dict = json.load(fp)
    task_config = TaskConfig.from_dict(task_dict)
    analysis_task = ScenarioAnalysisTask(task_config)

    analysis_task.run()


@shared_task(name="run_scenario_analysis_task")
def run_scenario_analysis_task():
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
    run_dummy_task()
    print(f'execution time: {time.time() - start_time} seconds')
    # use qgs.exit() if worker can be reused to execute another task
    # qgs.exit()
    qgs.exitQgis()
