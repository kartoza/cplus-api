import typing
import uuid
import json
import os
import logging
from django.utils import timezone
from cplus.models.base import (
    ImplementationModel,
    NcsPathway,
    Scenario,
    SpatialExtent,
    LayerType
)
from cplus.tasks.analysis import ScenarioAnalysisTask
from cplus.utils.conf import Settings
from cplus_api.models.scenario import ScenarioTask
from cplus_api.models.layer import BaseLayer, OutputLayer, InputLayer

logger = logging.getLogger(__name__)


class TaskConfig(object):

    scenario_name = ''
    scenario_desc = ''
    scenario_uuid = uuid.uuid4()
    analysis_implementation_models: typing.List[ImplementationModel] = []
    priority_layers: typing.List = []
    priority_layer_groups: typing.List = []
    analysis_extent: SpatialExtent = None
    snapping_enabled: bool = False
    snap_layer = ''
    pathway_suitability_index = 0
    carbon_coefficient = 0.0
    snap_rescale = False
    snap_method = 0
    scenario: Scenario = None
    pathway_uuid_layers = {}
    carbon_uuid_layers = {}
    priority_uuid_layers = {}
    total_input_layers = 0

    def __init__(self, scenario_name, scenario_desc, extent,
                 analysis_implementation_models, priority_layers,
                 priority_layer_groups,
                 snapping_enabled = False, snap_layer = '',
                 pathway_suitability_index = 0,
                 carbon_coefficient = 0.0, snap_rescale = False,
                 snap_method = 0, scenario_uuid = None) -> None:
        self.scenario_name = scenario_name
        self.scenario_desc = scenario_desc
        if scenario_uuid:
            self.scenario_uuid = uuid.UUID(scenario_uuid)
        self.analysis_extent = SpatialExtent(bbox=extent)
        self.analysis_implementation_models = analysis_implementation_models
        self.priority_layers = priority_layers
        self.priority_layer_groups = priority_layer_groups
        self.snapping_enabled = snapping_enabled
        self.snap_layer = snap_layer
        self.pathway_suitability_index = pathway_suitability_index
        self.carbon_coefficient = carbon_coefficient
        self.snap_rescale = snap_rescale
        self.snap_method = snap_method
        self.scenario = Scenario(
            uuid=self.scenario_uuid,
            name=self.scenario_name,
            description=self.scenario_desc,
            extent=self.analysis_extent,
            models=self.analysis_implementation_models,
            weighted_models=[],
            priority_layer_groups=self.priority_layer_groups
        )

    def get_implementation_model(
        self, implementation_model_uuid: str
    ) -> typing.Union[ImplementationModel, None]:
        implementation_model = None
        filtered = [
            im for im in self.analysis_implementation_models if
            str(im.uuid) == implementation_model_uuid
        ]
        if filtered:
            implementation_model = filtered[0]
        return implementation_model

    def get_priority_layers(self) -> typing.List:
        return self.priority_layers

    def get_priority_layer(self, identifier) -> typing.Dict:
        priority_layer = None
        filtered = [
            f for f in self.priority_layers if f['uuid'] == str(identifier)]
        if filtered:
            priority_layer = filtered[0]
        return priority_layer

    def get_value(self, attr_name: Settings, default = None):
        return getattr(self, attr_name.value, default)

    def to_dict(self):
        input_dict = {
            'scenario_name': self.scenario.name,
            'scenario_desc': self.scenario.description,
            'extent': self.analysis_extent.bbox,
            'priority_layers': self.priority_layers,
            'priority_layer_groups': self.priority_layer_groups,
            'implementation_models': [],
            'pathway_uuid_layers': self.pathway_uuid_layers,
            'carbon_uuid_layers': self.carbon_uuid_layers,
            'priority_uuid_layers': self.priority_uuid_layers,
            'total_input_layers': self.total_input_layers
        }
        for model in self.analysis_implementation_models:
            im_model_dict = {
                'uuid': str(model.uuid),
                'name': model.name,
                'description': model.description,
                'path': model.path,
                'layer_type': model.layer_type,
                'user_defined': model.user_defined,
                'pathways': [],
                'priority_layers': model.priority_layers,
                'layer_styles': model.layer_styles
            }
            for pathway in model.pathways:
                im_model_dict["pathways"].append({
                    'uuid': str(pathway.uuid),
                    'name': pathway.name,
                    'description': pathway.description,
                    'path': pathway.path,
                    'layer_type': pathway.layer_type,
                    'carbon_paths': pathway.carbon_paths
                })
            input_dict["implementation_models"].append(im_model_dict)
        return input_dict

    @classmethod
    def from_dict(cls, data: dict) -> typing.Self:
        config = TaskConfig(
            data.get('scenario_name', ''), data.get('scenario_desc', ''),
            data.get('extent', []), [], [], []
        )
        config.priority_layers = data.get('priority_layers', [])
        config.priority_layer_groups = data.get('priority_layer_groups', [])
        config.snapping_enabled = data.get('snapping_enabled', False)
        config.snap_layer = data.get('snap_layer', '')
        config.pathway_suitability_index = data.get(
            'pathway_suitability_index', 0)
        config.carbon_coefficient = data.get('carbon_coefficient', 0.0)
        config.snap_rescale = data.get('snap_rescale', False)
        config.snap_method = data.get('snap_method', 0)
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
        _models = data.get('implementation_models', [])
        for model in _models:
            uuid_str = model.get('uuid', None)
            m_priority_layers = model.get('priority_layers', [])
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
            im_model = ImplementationModel(
                uuid=uuid.UUID(uuid_str) if uuid_str else uuid.uuid4(),
                name=model.get('name', ''),
                description=model.get('description', ''),
                path='',
                layer_type=LayerType(model.get('layer_type', -1)),
                user_defined=model.get('user_defined', False),
                pathways=[],
                priority_layers=filtered_priority_layer,
                layer_styles=model.get('layer_styles', {})
            )
            pathways = model.get('pathways', [])
            for pathway in pathways:
                pw_uuid_str = pathway.get('uuid', None)
                pathway_model = NcsPathway(
                    uuid=(
                        uuid.UUID(pw_uuid_str) if pw_uuid_str else
                        uuid.uuid4()
                    ),
                    name=pathway.get('name', ''),
                    description=pathway.get('description', ''),
                    path=pathway.get('path', ''),
                    layer_type=LayerType(pathway.get('layer_type', -1)),
                    # store carbon layer uuids instead of the path
                    carbon_paths=pathway.get('carbon_uuids', [])
                )
                im_model.pathways.append(pathway_model)
                pw_layer_uuid = pathway.get('layer_uuid', None)
                if pw_layer_uuid:
                    if pw_layer_uuid in config.pathway_uuid_layers:
                        config.pathway_uuid_layers[pw_layer_uuid].append(
                            pw_uuid_str)
                    else:
                        config.pathway_uuid_layers[pw_layer_uuid] = [
                            pw_uuid_str
                        ]
                carbon_uuids = pathway.get('carbon_uuids', [])
                for carbon_uuid in carbon_uuids:
                    if carbon_uuid in config.carbon_uuid_layers:
                        config.carbon_uuid_layers[carbon_uuid].append(
                            pw_uuid_str)
                    else:
                        config.carbon_uuid_layers[carbon_uuid] = [
                            pw_uuid_str
                        ]

            config.analysis_implementation_models.append(im_model)
        config.scenario = Scenario(
            uuid=config.scenario_uuid,
            name=config.scenario_name,
            description=config.scenario_desc,
            extent=config.analysis_extent,
            models=config.analysis_implementation_models,
            weighted_models=[],
            priority_layer_groups=config.priority_layer_groups
        )
        config.total_input_layers = (
            len(config.pathway_uuid_layers) +
            len(config.priority_uuid_layers) +
            len(config.carbon_uuid_layers)
        )
        return config


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


class WorkerScenarioAnalysisTask(ScenarioAnalysisTask):

    MIN_UPDATE_PROGRESS_IN_SECONDS = 1

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
        self.last_update_progress = None

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
        # init priority layers
        priority_layer_paths = {}
        priority_uuids = self.task_config.priority_uuid_layers.keys()
        if priority_uuids:
            priority_layer_paths = self.copy_input_layers_by_uuids(
                InputLayer.ComponentTypes.PRIORITY_LAYER,
                priority_uuids,
                scenario_path
            )
        # init pathway layers
        pathway_layer_paths = {}
        pathway_uuids = self.task_config.pathway_uuid_layers.keys()
        if pathway_uuids:
            pathway_layer_paths = self.copy_input_layers_by_uuids(
                InputLayer.ComponentTypes.NCS_PATHWAY,
                pathway_uuids,
                scenario_path
            )
        # init carbon layers
        carbon_layer_paths = {}
        carbon_uuids = self.task_config.carbon_uuid_layers.keys()
        if carbon_uuids:
            carbon_layer_paths = self.copy_input_layers_by_uuids(
                InputLayer.ComponentTypes.NCS_CARBON,
                carbon_uuids,
                scenario_path
            )
        if priority_layer_paths:
            self.patch_layer_path_to_priority_layers(priority_layer_paths)
        self.patch_layer_path_to_implementation_models(
            priority_layer_paths,
            pathway_layer_paths,
            carbon_layer_paths
        )
        self.log_message(
            'Finished copy input layers: '
            f'{self.task_config.total_input_layers}'
        )

    def copy_input_layers_by_uuids(
            self, component_type: InputLayer.ComponentTypes,
            uuids: list, scenario_path: str):
        results = {}
        layers = InputLayer.objects.filter(
            component_type=component_type,
            uuid__in=uuids
        )
        for layer in layers:
            file_path = layer.download_to_working_directory(scenario_path)
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

    def patch_layer_path_to_implementation_models(
            self, priority_layer_paths,
            pathway_layer_paths, carbon_layer_paths):
        pw_uuid_mapped = self.transform_uuid_layer_paths(
            self.task_config.pathway_uuid_layers, pathway_layer_paths)
        carbon_uuid_mapped = self.transform_uuid_layer_paths(
            self.task_config.carbon_uuid_layers, carbon_layer_paths
        )
        priority_uuid_mapped = self.transform_uuid_layer_paths(
            self.task_config.priority_uuid_layers, priority_layer_paths
        )
        # iterate implementation models
        for model in self.task_config.analysis_implementation_models:
            for priority_layer in model.priority_layers:
                priority_layer_uuid = priority_layer.get('uuid', None)
                if not priority_layer_uuid:
                    continue
                if priority_layer_uuid not in priority_uuid_mapped:
                    continue
                priority_layer['path'] = (
                    priority_uuid_mapped[priority_layer_uuid]
                )
            for pathway in model.pathways:
                pathway_uuid = str(pathway.uuid)
                if pathway_uuid in pw_uuid_mapped:
                    pathway.path = pw_uuid_mapped[pathway_uuid]
                carbon_paths = []
                for carbon_layer_uuid in pathway.carbon_paths:
                    if carbon_layer_uuid in carbon_uuid_mapped:
                        carbon_paths.append(
                            carbon_uuid_mapped[carbon_layer_uuid])
                pathway.carbon_paths = carbon_paths
        self.scenario.models = self.task_config.analysis_implementation_models
        self.analysis_implementation_models = (
            self.task_config.analysis_implementation_models
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
        # info_message seems the same with log_message
        self.info_message = message

    def set_custom_progress(self, value):
        self.custom_progress = value
        self.scenario_task.progress = value
        # check how to control the frequency of updating progress
        # if too frequent, then the process becomes slower
        if self.should_update_progress():
            self.last_update_progress = timezone.now().second
            self.scenario_task.save(update_fields=['progress'])

    def should_update_progress(self):
        if self.last_update_progress is None:
            return True
        ct = timezone.now().second
        return (
            ct - self.last_update_progress >=
            self.MIN_UPDATE_PROGRESS_IN_SECONDS
        )

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
