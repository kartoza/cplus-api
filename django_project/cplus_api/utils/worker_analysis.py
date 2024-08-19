import json
import os
import logging
import traceback
import subprocess
from django.conf import settings
from django.utils import timezone
from django.template.loader import render_to_string
from django.core.mail import send_mail
from cplus_core.analysis import ScenarioAnalysisTask, TaskConfig
from cplus_api.models.scenario import ScenarioTask
from cplus_api.models.layer import OutputLayer, InputLayer
from cplus_api.utils.api_helper import (
    convert_size,
    todict,
    CustomJsonEncoder,
    get_layer_type
)

logger = logging.getLogger(__name__)


class WorkerScenarioAnalysisTask:

    MIN_UPDATE_PROGRESS_IN_SECONDS = 1

    def __init__(self, task_config: TaskConfig,
                 scenario_task: ScenarioTask):
        self.task = ScenarioAnalysisTask(task_config)
        self.scenario_task = scenario_task
        self.last_update_progress = None
        self.downloaded_layers = {}
        self.downloaded_layer_count = 0

    def prepare_run(self):
        self.task.scenario_directory = self.scenario_task.get_resources_path()
        self.task.status_message_changed.connect(self.set_status_message)
        self.task.info_message_changed.connect(self.set_info_message)
        self.task.custom_progress_changed.connect(self.set_custom_progress)
        self.task.log_received.connect(self.log_message)
        self.task.task_cancelled.connect(self.cancel_task)
        # clear existing scenario directory if exists
        self.scenario_task.clear_resources()
        # create scenario directory for a user
        scenario_path = self.scenario_task.get_resources_path()
        os.makedirs(scenario_path)
        # clear existing output results
        OutputLayer.objects.filter(
            scenario=self.scenario_task
        ).delete()
        # download input layers
        self.initialize_input_layers(scenario_path)

    def initialize_input_layers(self, scenario_path: str):
        self.log_message(
            f'Initialize input layers: {self.task.task_config.total_input_layers}')
        self.set_custom_progress(0)
        self.set_status_message('Preparing input layers')

        # init priority layers
        priority_layer_paths = {}
        priority_uuids = self.task.task_config.priority_uuid_layers.keys()
        if priority_uuids:
            priority_layer_paths = self.copy_input_layers_by_uuids(
                InputLayer.ComponentTypes.PRIORITY_LAYER,
                priority_uuids,
                scenario_path
            )
            self.downloaded_layers.update(priority_layer_paths)
        # init pathway layers
        pathway_layer_paths = {}
        pathway_uuids = self.task.task_config.pathway_uuid_layers.keys()
        if pathway_uuids:
            pathway_uuids_to_download = [
                p_uuid for p_uuid in pathway_uuids if
                str(p_uuid) not in self.downloaded_layers
            ]
            pathway_layer_paths = self.copy_input_layers_by_uuids(
                InputLayer.ComponentTypes.NCS_PATHWAY,
                pathway_uuids_to_download,
                scenario_path
            )
            self.downloaded_layers.update(pathway_layer_paths)
            pathway_layer_paths.update({
                key: val for key, val in self.downloaded_layers.items()
                if key in pathway_uuids
            })

        # init carbon layers
        carbon_layer_paths = {}
        carbon_uuids = self.task.task_config.carbon_uuid_layers.keys()
        if carbon_uuids:
            carbon_uuids_to_download = [
                c_uuid for c_uuid in carbon_uuids if
                str(c_uuid) not in self.downloaded_layers
            ]
            carbon_layer_paths = self.copy_input_layers_by_uuids(
                InputLayer.ComponentTypes.NCS_CARBON,
                carbon_uuids_to_download,
                scenario_path
            )
            self.downloaded_layers.update(carbon_layer_paths)
            carbon_layer_paths.update({
                key: val for key, val in self.downloaded_layers.items()
                if key in carbon_uuids
            })

        if priority_layer_paths:
            self.patch_layer_path_to_priority_layers(priority_layer_paths)
        self.patch_layer_path_to_activities(
            priority_layer_paths,
            pathway_layer_paths,
            carbon_layer_paths
        )

        # init snap layer
        if self.task.task_config.snap_layer_uuid:
            layer_uuid = self.task.task_config.snap_layer_uuid
            if layer_uuid not in self.downloaded_layers:
                layer_paths = self.copy_input_layers_by_uuids(
                    None, [layer_uuid], scenario_path
                )
                if layer_uuid in layer_paths:
                    self.task.task_config.snap_layer = layer_paths[layer_uuid]
                    self.downloaded_layers.update(layer_paths)
            else:
                self.task.task_config.snap_layer = self.downloaded_layers[
                    layer_uuid
                ]

        # init sieve mask path
        if self.task.task_config.sieve_mask_uuid:
            layer_uuid = self.task.task_config.sieve_mask_uuid
            if layer_uuid not in self.downloaded_layers:
                layer_paths = self.copy_input_layers_by_uuids(
                    None, [layer_uuid], scenario_path
                )
                if layer_uuid in layer_paths:
                    self.task.task_config.mask_path = layer_paths[layer_uuid]
                    self.downloaded_layers.update(layer_paths)
            else:
                self.task.task_config.mask_path = self.downloaded_layers[
                    layer_uuid
                ]

        # init mask layers
        new_mask_paths = []
        for mask_layer in self.task.task_config.mask_layer_uuids:
            layer_uuid = mask_layer
            if layer_uuid not in self.downloaded_layers:
                layer_paths = self.copy_input_layers_by_uuids(
                    None, [layer_uuid], scenario_path
                )
                if layer_uuid in layer_paths:
                    new_mask_paths.append(layer_paths[layer_uuid])
                    self.downloaded_layers.update(layer_paths)
            else:
                new_mask_paths.append(self.downloaded_layers[layer_uuid])
        self.task.task_config.mask_layers_paths = ','.join(new_mask_paths)

        self.log_message(
            'Finished copy input layers: '
            f'{self.task.task_config.total_input_layers}'
        )
        self.set_custom_progress(100)

    def copy_input_layers_by_uuids(
            self, component_type: InputLayer.ComponentTypes,
            uuids: list, scenario_path: str):
        results = {}
        layers = InputLayer.objects.filter(
            uuid__in=uuids
        )
        if component_type:
            layers = layers.filter(
                component_type=component_type
            )
        total_input_layers = (
            self.task.task_config.total_input_layers if
            self.task.task_config.total_input_layers > 0 else 1
        )
        for layer in layers:
            file_path = layer.download_to_working_directory(scenario_path)
            self.downloaded_layer_count += 1
            self.set_custom_progress(
                100 * (
                    self.downloaded_layer_count /
                    total_input_layers
                )
            )
            if not file_path:
                continue
            if not os.path.exists(file_path):
                continue
            results[str(layer.uuid)] = file_path
        return results

    def patch_layer_path_to_priority_layers(self, priority_layer_paths):
        for priority_layer in self.task.task_config.priority_layers:
            layer_uuid = priority_layer.get('layer_uuid', None)
            if not layer_uuid or layer_uuid not in priority_layer_paths:
                continue
            priority_layer['path'] = priority_layer_paths[layer_uuid]

    def patch_layer_path_to_activities(
            self, priority_layer_paths,
            pathway_layer_paths, carbon_layer_paths):
        pw_uuid_mapped = self.transform_uuid_layer_paths(
            self.task.task_config.pathway_uuid_layers, pathway_layer_paths)
        priority_uuid_mapped = self.transform_uuid_layer_paths(
            self.task.task_config.priority_uuid_layers, priority_layer_paths
        )
        # iterate activities
        for activity in self.task.task_config.analysis_activities:
            for priority_layer in activity.priority_layers:
                priority_layer_uuid = priority_layer.get('uuid', None)
                if not priority_layer_uuid:
                    continue
                if priority_layer_uuid not in priority_uuid_mapped:
                    continue
                priority_layer['path'] = (
                    priority_uuid_mapped[priority_layer_uuid]
                )
            for pathway in activity.pathways:
                pathway_uuid = str(pathway.uuid)
                if pathway_uuid in pw_uuid_mapped:
                    pathway.path = pw_uuid_mapped[pathway_uuid]
                carbon_paths = []
                for carbon_layer_uuid in pathway.carbon_paths:
                    if carbon_layer_uuid in carbon_layer_paths:
                        carbon_paths.append(
                            carbon_layer_paths[carbon_layer_uuid])
                pathway.carbon_paths = carbon_paths
        self.task.analysis_activities = (
            self.task.task_config.analysis_activities
        )

    def transform_uuid_layer_paths(self, uuid_layers, layer_paths):
        uuid_mapped = {}
        for layer_uuid, uuid_list in uuid_layers.items():
            if layer_uuid not in layer_paths:
                continue
            for uuid_str in uuid_list:
                uuid_mapped[uuid_str] = layer_paths[layer_uuid]
        return uuid_mapped

    def cancel_task(self):
        # raise exception to stop the task
        if self.task.error:
            raise self.task.error
        else:
            raise Exception('Task is stopped with errors!')

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
        # info_message seems the same with log_message
        self.info_message = message

    def set_custom_progress(self, value):
        self.scenario_task.progress = value
        # check how to control the frequency of updating progress
        # if too frequent, then the process becomes slower
        should_update_progress = self.should_update_progress()
        if should_update_progress:
            self.last_update_progress = timezone.now()
            self.scenario_task.save(update_fields=['progress'])

    def should_update_progress(self):
        if self.last_update_progress is None:
            return True
        ct = timezone.now()
        return (
            (ct - self.last_update_progress).total_seconds() >=
            self.MIN_UPDATE_PROGRESS_IN_SECONDS
        )

    def create_and_upload_output_layer(
            self, file_path: str, scenario_task: ScenarioTask,
            is_final_output: bool, group: str,
            output_meta: dict = None) -> OutputLayer:
        filename = os.path.basename(file_path)
        if get_layer_type(file_path) == 0:
            cog_name = (
                f"{os.path.basename(file_path).split('.')[0]}"
                f"_COG."
                f"{os.path.basename(file_path).split('.')[1]}"
            )
            final_output_path = os.path.join(
                os.path.dirname(file_path),
                cog_name
            )
            result = subprocess.run(
                (
                    f'gdal_translate -of COG -co COMPRESS=DEFLATE'
                    f' "{file_path}" "{final_output_path}"'
                ),
                shell=True,
                capture_output=True
            )
            if result.returncode != 0:
                self.log_message(result.stderr.decode(), info=False)
                self.log_message(
                    f"Failed coverting raster to COG: {file_path}",
                    info=False
                )
            if not os.path.exists(final_output_path):
                # fallback to original file
                final_output_path = file_path
        else:
            final_output_path = file_path
        output_layer = OutputLayer.objects.create(
            name=filename,
            created_on=timezone.now(),
            owner=scenario_task.submitted_by,
            layer_type=get_layer_type(file_path),
            size=os.stat(final_output_path).st_size,
            is_final_output=is_final_output,
            scenario=scenario_task,
            group=group,
            output_meta={} if not output_meta else output_meta
        )
        with open(final_output_path, 'rb') as output_file:
            output_layer.file.save(filename, output_file)
        return output_layer

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
                output_meta = self.task.output
                if 'OUTPUT' in output_meta:
                    del output_meta['OUTPUT']
                self.create_and_upload_output_layer(
                    files[0], self.scenario_task,
                    True, None, self.task.output
                )
                total_uploaded_files += 1
                self.set_custom_progress(
                    100 * (total_uploaded_files / total_files))
            else:
                for file in files:
                    self.create_and_upload_output_layer(
                        file, self.scenario_task, False, group)
                    total_uploaded_files += 1
                    self.set_custom_progress(
                        100 * (total_uploaded_files / total_files))

    def notify_user(self, is_success: bool):
        if not self.scenario_task.submitted_by.email:
            return
        try:
            scenario_name = self.scenario_task.get_detail_value(
                'scenario_name', f'scenario {self.scenario_task.uuid}')
            activities = []
            activities_raw = self.scenario_task.get_detail_value(
                'activities', [])
            for activity in activities_raw:
                pathways = [
                    pathway['name'] for pathway in
                    activity.get('pathways', [])
                ]
                activities.append({
                    'name': activity.get('name', ''),
                    'pathways': ', '.join(pathways)
                })
            priority_layer_groups = []
            pl_groups = self.scenario_task.get_detail_value(
                'priority_layer_groups', [])
            for pl in pl_groups:
                layers = pl.get('layers', [])
                if not layers:
                    continue
                priority_layer_groups.append({
                    'name': pl.get('name', ''),
                    'value': pl.get('value', '0'),
                    'layers': ', '.join(layers)
                })
            output_layers = []
            layers = OutputLayer.objects.filter(
                scenario=self.scenario_task
            ).order_by('group')
            for layer in layers:
                output_layers.append({
                    'name': layer.name,
                    'type': (
                        layer.group if not layer.is_final_output else
                        'Final Output'
                    ),
                    'size': convert_size(layer.size)
                })
            message = render_to_string(
                'emails/analysis_completed.html',
                {
                    'name': (
                        self.scenario_task.submitted_by.first_name if
                        self.scenario_task.submitted_by.first_name else
                        self.scenario_task.submitted_by.username
                    ),
                    'scenario_name': scenario_name,
                    'is_success': is_success,
                    'scenario_desc': (
                        self.scenario_task.get_detail_value(
                            'scenario_desc', '')
                    ),
                    'activities': activities,
                    'priority_layer_groups': priority_layer_groups,
                    'started_at': self.scenario_task.started_at,
                    'processing_time': (
                        self.scenario_task.get_processing_time()
                    ),
                    'output_layers': output_layers,
                    'progress_text': self.scenario_task.progress_text,
                    'errors': self.scenario_task.errors
                },
            )
            subject = (
                f'Your analysis of {scenario_name} '
                'has finished successfully' if
                is_success else
                f'Your analysis of {scenario_name} has stopped with errors'
            )
            send_mail(
                subject,
                None,
                settings.SERVER_EMAIL,
                [self.scenario_task.submitted_by.email],
                html_message=message
            )
        except Exception as exc:
            logger.error(f'Unexpected exception occured: {type(exc).__name__} '
                         'when sending email')
            logger.error(exc)
            logger.error(traceback.format_exc())

    def run(self):
        self.task.run()

    def finished(self, result: bool):
        if result:
            self.upload_scenario_outputs()
        else:
            self.log_message(
                f"Error from task scenario task {self.task.error}", info=False)
        # clean directory
        self.scenario_task.clear_resources()
        self.scenario_task.task_on_completed()
        self.scenario_task.updated_detail = json.loads(
            json.dumps(todict(self.task.scenario), cls=CustomJsonEncoder)
        )
        self.scenario_task.save()
        # send email to the submitter
        self.notify_user(result)
