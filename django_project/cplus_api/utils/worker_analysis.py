import typing
import uuid
import json
import os
import logging
import traceback
import subprocess
from django.conf import settings
from django.utils import timezone
from django.template.loader import render_to_string
from django.core.mail import send_mail
from cplus.models.base import (
    Activity,
    NcsPathway,
    Scenario,
    SpatialExtent,
    LayerType
)
from cplus.tasks.analysis import ScenarioAnalysisTask
from cplus.utils.conf import Settings
from cplus_api.models.scenario import ScenarioTask
from cplus_api.models.layer import OutputLayer, InputLayer
from cplus_api.utils.api_helper import (
    convert_size,
    todict,
    CustomJsonEncoder,
    get_layer_type
)
from cplus_api.utils.default import DEFAULT_VALUES

logger = logging.getLogger(__name__)


class TaskConfig(object):

    scenario_name = ''
    scenario_desc = ''
    scenario_uuid = uuid.uuid4()
    analysis_activities: typing.List[Activity] = []
    priority_layers: typing.List = []
    priority_layer_groups: typing.List = []
    analysis_extent: SpatialExtent = None
    snapping_enabled: bool = DEFAULT_VALUES.snapping_enabled
    snap_layer = ''
    snap_layer_uuid = ''
    pathway_suitability_index = DEFAULT_VALUES.pathway_suitability_index
    carbon_coefficient = DEFAULT_VALUES.carbon_coefficient
    snap_rescale = DEFAULT_VALUES.snap_rescale
    snap_method = DEFAULT_VALUES.snap_method
    sieve_enabled = DEFAULT_VALUES.sieve_enabled
    sieve_threshold = DEFAULT_VALUES.sieve_threshold
    sieve_mask_uuid = ''
    mask_path = ''
    mask_layers_paths = ''
    mask_layer_uuids = []
    scenario: Scenario = None
    pathway_uuid_layers = {}
    carbon_uuid_layers = {}
    priority_uuid_layers = {}
    total_input_layers = 0
    # output selections
    ncs_with_carbon = DEFAULT_VALUES.ncs_with_carbon
    landuse_project = DEFAULT_VALUES.landuse_project
    landuse_normalized = DEFAULT_VALUES.landuse_normalized
    landuse_weighted = DEFAULT_VALUES.landuse_weighted
    highest_position = DEFAULT_VALUES.highest_position

    def __init__(self, scenario_name, scenario_desc, extent,
                 analysis_activities, priority_layers,
                 priority_layer_groups,
                 snapping_enabled=False, snap_layer_uuid='',
                 pathway_suitability_index=DEFAULT_VALUES.pathway_suitability_index,  # noqa
                 carbon_coefficient=DEFAULT_VALUES.carbon_coefficient,
                 snap_rescale=DEFAULT_VALUES.snap_rescale,
                 snap_method=DEFAULT_VALUES.snap_method,
                 sieve_enabled=DEFAULT_VALUES.sieve_enabled,
                 sieve_threshold=DEFAULT_VALUES.sieve_threshold,
                 sieve_mask_uuid='',
                 mask_layer_uuids='', scenario_uuid=None,
                 ncs_with_carbon=DEFAULT_VALUES.ncs_with_carbon,
                 landuse_project=DEFAULT_VALUES.landuse_project,
                 landuse_normalized=DEFAULT_VALUES.landuse_normalized,
                 landuse_weighted=DEFAULT_VALUES.landuse_weighted,
                 highest_position=DEFAULT_VALUES.highest_position) -> None:
        self.scenario_name = scenario_name
        self.scenario_desc = scenario_desc
        if scenario_uuid:
            self.scenario_uuid = uuid.UUID(scenario_uuid)
        self.analysis_extent = SpatialExtent(bbox=extent)
        self.analysis_activities = analysis_activities
        self.priority_layers = priority_layers
        self.priority_layer_groups = priority_layer_groups
        self.snapping_enabled = snapping_enabled
        self.snap_layer_uuid = snap_layer_uuid
        self.pathway_suitability_index = pathway_suitability_index
        self.carbon_coefficient = carbon_coefficient
        self.snap_rescale = snap_rescale
        self.snap_method = snap_method
        self.sieve_enabled = sieve_enabled
        self.sieve_threshold = sieve_threshold
        self.sieve_mask_uuid = sieve_mask_uuid
        self.mask_layer_uuids = mask_layer_uuids
        self.scenario = Scenario(
            uuid=self.scenario_uuid,
            name=self.scenario_name,
            description=self.scenario_desc,
            extent=self.analysis_extent,
            activities=self.analysis_activities,
            weighted_activities=[],
            priority_layer_groups=self.priority_layer_groups
        )
        # output selections
        self.ncs_with_carbon = ncs_with_carbon
        self.landuse_project = landuse_project
        self.landuse_normalized = landuse_normalized
        self.landuse_weighted = landuse_weighted
        self.highest_position = highest_position

    def get_activity(
        self, activity_uuid: str
    ) -> typing.Union[Activity, None]:
        activity = None
        filtered = [
            act for act in self.analysis_activities if
            str(act.uuid) == activity_uuid
        ]
        if filtered:
            activity = filtered[0]
        return activity

    def get_priority_layers(self) -> typing.List:
        return self.priority_layers

    def get_priority_layer(self, identifier) -> typing.Dict:
        priority_layer = None
        filtered = [
            f for f in self.priority_layers if f['uuid'] == str(identifier)]
        if filtered:
            priority_layer = filtered[0]
        return priority_layer

    def get_value(self, attr_name: Settings, default=None):
        return getattr(self, attr_name.value, default)

    def to_dict(self):
        input_dict = {
            'scenario_name': self.scenario.name,
            'scenario_desc': self.scenario.description,
            'extent': self.analysis_extent.bbox,
            'snapping_enabled': self.snapping_enabled,
            'snap_layer': self.snap_layer_uuid,
            'pathway_suitability_index': self.pathway_suitability_index,
            'carbon_coefficient': self.carbon_coefficient,
            'snap_rescale': self.snap_rescale,
            'snap_method': self.snap_method,
            'sieve_enabled': self.sieve_enabled,
            'sieve_threshold': self.sieve_threshold,
            'sieve_mask_uuid': self.sieve_mask_uuid,
            'mask_layer_uuids': self.mask_layer_uuids,
            'priority_layers': self.priority_layers,
            'priority_layer_groups': self.priority_layer_groups,
            'activities': [],
            'pathway_uuid_layers': self.pathway_uuid_layers,
            'carbon_uuid_layers': self.carbon_uuid_layers,
            'priority_uuid_layers': self.priority_uuid_layers,
            'total_input_layers': self.total_input_layers,
            'ncs_with_carbon': self.ncs_with_carbon,
            'landuse_project': self.landuse_project,
            'landuse_normalized': self.landuse_normalized,
            'landuse_weighted': self.landuse_weighted,
            'highest_position': self.highest_position
        }
        for activity in self.analysis_activities:
            activity_dict = {
                'uuid': str(activity.uuid),
                'name': activity.name,
                'description': activity.description,
                'path': activity.path,
                'layer_type': activity.layer_type,
                'user_defined': activity.user_defined,
                'pathways': [],
                'priority_layers': activity.priority_layers,
                'layer_styles': activity.layer_styles
            }
            for pathway in activity.pathways:
                activity_dict["pathways"].append({
                    'uuid': str(pathway.uuid),
                    'name': pathway.name,
                    'description': pathway.description,
                    'path': pathway.path,
                    'layer_type': pathway.layer_type,
                    'carbon_paths': pathway.carbon_paths
                })
            input_dict["activities"].append(activity_dict)
        return input_dict

    @classmethod
    def from_dict(cls, data: dict) -> typing.Self:
        config = TaskConfig(
            data.get('scenario_name', ''), data.get('scenario_desc', ''),
            data.get('extent', []), [], [], []
        )
        config.priority_layers = data.get('priority_layers', [])
        config.priority_layer_groups = data.get('priority_layer_groups', [])
        config.snapping_enabled = data.get(
            'snapping_enabled', DEFAULT_VALUES.snapping_enabled)
        config.snap_layer_uuid = data.get('snap_layer_uuid', '')
        config.pathway_suitability_index = data.get(
            'pathway_suitability_index',
            DEFAULT_VALUES.pathway_suitability_index)
        config.carbon_coefficient = data.get(
            'carbon_coefficient', DEFAULT_VALUES.carbon_coefficient)
        config.snap_rescale = data.get(
            'snap_rescale', DEFAULT_VALUES.snap_rescale)
        config.snap_method = data.get(
            'snap_method', DEFAULT_VALUES.snap_method)
        config.sieve_enabled = data.get(
            'sieve_enabled', DEFAULT_VALUES.sieve_enabled)
        config.sieve_threshold = data.get(
            'sieve_threshold', DEFAULT_VALUES.sieve_threshold)
        config.sieve_mask_uuid = data.get('sieve_mask_uuid', '')
        config.mask_layer_uuids = data.get('mask_layer_uuids', '')
        config.ncs_with_carbon = data.get(
            'ncs_with_carbon', DEFAULT_VALUES.ncs_with_carbon)
        config.landuse_project = data.get(
            'landuse_project', DEFAULT_VALUES.landuse_project)
        config.landuse_normalized = data.get(
            'landuse_normalized', DEFAULT_VALUES.landuse_normalized)
        config.landuse_weighted = data.get(
            'landuse_weighted', DEFAULT_VALUES.landuse_weighted)
        config.highest_position = data.get(
            'highest_position', DEFAULT_VALUES.highest_position)
        # store dict of <layer_uuid, list of obj identifier>
        config.priority_uuid_layers = {}
        config.pathway_uuid_layers = {}
        config.carbon_uuid_layers = {}
        for priority_layer in config.priority_layers:
            priority_layer_uuid = priority_layer.get('uuid', None)
            if not priority_layer_uuid:
                continue
            layer_uuid = priority_layer.get('layer_uuid', None)
            if not layer_uuid:
                continue
            if layer_uuid in config.priority_uuid_layers:
                config.priority_uuid_layers[layer_uuid].append(
                    priority_layer_uuid)
            else:
                config.priority_uuid_layers[layer_uuid] = [
                    priority_layer_uuid
                ]
        _activities = data.get('activities', [])
        for activity in _activities:
            uuid_str = activity.get('uuid', None)
            m_priority_layers = activity.get('priority_layers', [])
            filtered_priority_layer = []
            for m_priority_layer in m_priority_layers:
                if not m_priority_layer:
                    continue
                filtered_priority_layer.append(m_priority_layer)
                m_priority_uuid = m_priority_layer.get('uuid', None)
                if not m_priority_uuid:
                    continue
                m_priority_layer_uuid = m_priority_layer.get(
                    'layer_uuid', None)
                if not m_priority_layer_uuid:
                    continue
                if m_priority_layer_uuid in config.priority_uuid_layers:
                    config.priority_uuid_layers[m_priority_layer_uuid].append(
                        m_priority_uuid)
                else:
                    config.priority_uuid_layers[m_priority_layer_uuid] = [
                        m_priority_uuid
                    ]
            activity_obj = Activity(
                uuid=uuid.UUID(uuid_str) if uuid_str else uuid.uuid4(),
                name=activity.get('name', ''),
                description=activity.get('description', ''),
                path='',
                layer_type=LayerType(activity.get('layer_type', -1)),
                user_defined=activity.get('user_defined', False),
                pathways=[],
                priority_layers=filtered_priority_layer,
                layer_styles=activity.get('layer_styles', {})
            )
            pathways = activity.get('pathways', [])
            for pathway in pathways:
                pw_uuid_str = pathway.get('uuid', None)
                pw_uuid = (
                    uuid.UUID(pw_uuid_str) if pw_uuid_str else
                    uuid.uuid4()
                )
                pathway_model = NcsPathway(
                    uuid=pw_uuid,
                    name=pathway.get('name', ''),
                    description=pathway.get('description', ''),
                    path=pathway.get('path', ''),
                    layer_type=LayerType(pathway.get('layer_type', -1)),
                    # store carbon layer uuids instead of the path
                    carbon_paths=pathway.get('carbon_uuids', [])
                )
                activity_obj.pathways.append(pathway_model)
                pw_layer_uuid = pathway.get('layer_uuid', None)
                if pw_layer_uuid:
                    if pw_layer_uuid in config.pathway_uuid_layers:
                        config.pathway_uuid_layers[pw_layer_uuid].append(
                            str(pw_uuid))
                    else:
                        config.pathway_uuid_layers[pw_layer_uuid] = [
                            str(pw_uuid)
                        ]
                carbon_uuids = pathway.get('carbon_uuids', [])
                for carbon_uuid in carbon_uuids:
                    if carbon_uuid in config.carbon_uuid_layers:
                        config.carbon_uuid_layers[carbon_uuid].append(
                            str(pw_uuid))
                    else:
                        config.carbon_uuid_layers[carbon_uuid] = [
                            str(pw_uuid)
                        ]

            config.analysis_activities.append(activity_obj)
        config.scenario = Scenario(
            uuid=config.scenario_uuid,
            name=config.scenario_name,
            description=config.scenario_desc,
            extent=config.analysis_extent,
            activities=config.analysis_activities,
            weighted_activities=[],
            priority_layer_groups=config.priority_layer_groups
        )
        config.total_input_layers = (
            len(config.pathway_uuid_layers) +
            len(config.priority_uuid_layers) +
            len(config.carbon_uuid_layers)
        )
        if config.snap_layer_uuid:
            config.total_input_layers += 1
        if config.sieve_mask_uuid:
            config.total_input_layers += 1
        config.total_input_layers += len(config.mask_layer_uuids)
        return config


class WorkerScenarioAnalysisTask(ScenarioAnalysisTask):

    MIN_UPDATE_PROGRESS_IN_SECONDS = 1

    def __init__(self, task_config: TaskConfig,
                 scenario_task: ScenarioTask):
        super().__init__(
            task_config.scenario_name,
            task_config.scenario_desc,
            task_config.analysis_activities,
            task_config.priority_layer_groups,
            task_config.analysis_extent,
            task_config.scenario
        )
        self.task_config = task_config
        self.scenario_task = scenario_task
        self.last_update_progress = None
        self.downloaded_layers = {}
        self.downloaded_layer_count = 0

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
        # download input layers
        self.initialize_input_layers(scenario_path)

    def initialize_input_layers(self, scenario_path: str):
        self.log_message(
            f'Initialize input layers: {self.task_config.total_input_layers}')
        self.set_custom_progress(0)
        self.set_status_message('Preparing input layers')

        # init priority layers
        priority_layer_paths = {}
        priority_uuids = self.task_config.priority_uuid_layers.keys()
        if priority_uuids:
            priority_layer_paths = self.copy_input_layers_by_uuids(
                InputLayer.ComponentTypes.PRIORITY_LAYER,
                priority_uuids,
                scenario_path
            )
            self.downloaded_layers.update(priority_layer_paths)
        # init pathway layers
        pathway_layer_paths = {}
        pathway_uuids = self.task_config.pathway_uuid_layers.keys()
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
        carbon_uuids = self.task_config.carbon_uuid_layers.keys()
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
        if self.task_config.snap_layer_uuid:
            layer_uuid = self.task_config.snap_layer_uuid
            if layer_uuid not in self.downloaded_layers:
                layer_paths = self.copy_input_layers_by_uuids(
                    None, [layer_uuid], scenario_path
                )
                if layer_uuid in layer_paths:
                    self.task_config.snap_layer = layer_paths[layer_uuid]
                    self.downloaded_layers.update(layer_paths)
            else:
                self.task_config.snap_layer = self.downloaded_layers[
                    layer_uuid
                ]

        # init sieve mask path
        if self.task_config.sieve_mask_uuid:
            layer_uuid = self.task_config.sieve_mask_uuid
            if layer_uuid not in self.downloaded_layers:
                layer_paths = self.copy_input_layers_by_uuids(
                    None, [layer_uuid], scenario_path
                )
                if layer_uuid in layer_paths:
                    self.task_config.mask_path = layer_paths[layer_uuid]
                    self.downloaded_layers.update(layer_paths)
            else:
                self.task_config.mask_path = self.downloaded_layers[
                    layer_uuid
                ]

        # init mask layers
        new_mask_paths = []
        for mask_layer in self.task_config.mask_layer_uuids:
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
        self.task_config.mask_layers_paths = ','.join(new_mask_paths)

        self.log_message(
            'Finished copy input layers: '
            f'{self.task_config.total_input_layers}'
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
            self.task_config.total_input_layers if
            self.task_config.total_input_layers > 0 else 1
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
        for priority_layer in self.task_config.priority_layers:
            layer_uuid = priority_layer.get('layer_uuid', None)
            if not layer_uuid or layer_uuid not in priority_layer_paths:
                continue
            priority_layer['path'] = priority_layer_paths[layer_uuid]

    def patch_layer_path_to_activities(
            self, priority_layer_paths,
            pathway_layer_paths, carbon_layer_paths):
        pw_uuid_mapped = self.transform_uuid_layer_paths(
            self.task_config.pathway_uuid_layers, pathway_layer_paths)
        priority_uuid_mapped = self.transform_uuid_layer_paths(
            self.task_config.priority_uuid_layers, priority_layer_paths
        )
        # iterate activities
        for activity in self.task_config.analysis_activities:
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
        self.scenario.activities = self.task_config.analysis_activities
        self.analysis_activities = (
            self.task_config.analysis_activities
        )

    def transform_uuid_layer_paths(self, uuid_layers, layer_paths):
        uuid_mapped = {}
        for layer_uuid, uuid_list in uuid_layers.items():
            if layer_uuid not in layer_paths:
                continue
            for uuid_str in uuid_list:
                uuid_mapped[uuid_str] = layer_paths[layer_uuid]
        return uuid_mapped

    def get_settings_value(self, name: str,
                           default=None, setting_type=None):
        return self.task_config.get_value(name, default)

    def get_scenario_directory(self):
        return self.scenario_task.get_resources_path()

    def get_priority_layer(self, identifier):
        return self.task_config.get_priority_layer(identifier)

    def get_activity(self, activity_uuid):
        return self.task_config.get_activity(activity_uuid)

    def get_priority_layers(self):
        return self.task_config.get_priority_layers()

    def cancel_task(self, exception=None):
        self.error = exception
        # raise exception to stop the task
        if exception:
            raise exception
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
        self.custom_progress = value
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
                    f'gdal_translate -of COG -co COMPRESS=DEFLATE '
                    f'-co RESAMPLING=BILINEAR '
                    f'-co OVERVIEW_RESAMPLING=NEAREST '
                    f'-co NUM_THREADS=ALL_CPUS '
                    f'-co BLOCKSIZE=512 '
                    f'"{file_path}" "{final_output_path}"'
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
                output_meta = self.output
                if 'OUTPUT' in output_meta:
                    del output_meta['OUTPUT']
                self.create_and_upload_output_layer(
                    files[0], self.scenario_task,
                    True, None, self.output
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

    def finished(self, result: bool):
        if result:
            self.upload_scenario_outputs()
        else:
            self.log_message(
                f"Error from task scenario task {self.error}", info=False)
        # clean directory
        self.scenario_task.clear_resources()
        self.scenario_task.task_on_completed()
        self.scenario_task.updated_detail = json.loads(
            json.dumps(todict(self.scenario), cls=CustomJsonEncoder)
        )
        self.scenario_task.save()
        # send email to the submitter
        self.notify_user(result)
