import typing
import uuid
import json
import os
import logging
import traceback
import subprocess
from django.core.mail import send_mail
from django.contrib.sites.models import Site
from django.conf import settings
from django.utils import timezone
from django.template.loader import render_to_string
from cplus_core.models.base import (
    Activity,
    NcsPathway,
    Scenario,
    SpatialExtent,
    LayerType
)
from cplus_core.analysis import ScenarioAnalysisTask, TaskConfig
from cplus_core.utils.conf import Settings
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


class APITaskConfig(object):
    """Class to parse the task config sent from API."""

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
    snap_rescale: bool = DEFAULT_VALUES.snap_rescale
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
    activity_mask_uuid_layers = {}
    activity_mask_layer_paths = []
    total_input_layers = 0
    # output selections
    ncs_with_carbon = DEFAULT_VALUES.ncs_with_carbon
    landuse_project = DEFAULT_VALUES.landuse_project
    landuse_normalized = DEFAULT_VALUES.landuse_normalized
    landuse_weighted = DEFAULT_VALUES.landuse_weighted
    highest_position = DEFAULT_VALUES.highest_position

    clip_to_studyarea: bool = DEFAULT_VALUES.clip_to_studyarea
    studyarea_path = ''
    studyarea_layer_uuid = ''

    relative_impact_matrix: typing.Dict = {}
    activity_constant_rasters: typing.Dict = {}
    constant_rasters_uuids = typing.Dict = {}
    pixel_connectivity_enabled: bool = (
        DEFAULT_VALUES.pixel_connectivity_enabled
    )

    def __init__(self, scenario_name, scenario_desc, extent, analysis_crs,
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
                 highest_position=DEFAULT_VALUES.highest_position,
                 nodata_value=DEFAULT_VALUES.nodata_value,
                 clip_to_studyarea=DEFAULT_VALUES.clip_to_studyarea,
                 studyarea_layer_uuid='',
                 relative_impact_matrix={},
                 constant_rasters_uuids={},
                 pixel_connectivity_enabled=False
                 ) -> None:
        """Initialize APITaskConfig class.

        :param scenario_name: name of the scenario
        :type scenario_name: str
        :param scenario_desc: description of the scenario
        :type scenario_desc: str
        :param extent: scenario extent
        :type extent: List[float]
        :param analysis_crs: scenario analysis CRS
        :type analysis_crs: str
        :param analysis_activities: scenario activities
        :type analysis_activities: List[Activity]
        :param priority_layers: list of priority layer dict
        :type priority_layers: List
        :param priority_layer_groups: List of priority layer group dict
        :type priority_layer_groups: List
        :param snapping_enabled: enable snapping, defaults to False
        :type snapping_enabled: bool, optional
        :param snap_layer_uuid: Layer UUID of snap layer, defaults to ''
        :type snap_layer_uuid: str, optional
        :param pathway_suitability_index: Pathway suitability index,
            defaults to DEFAULT_VALUES.pathway_suitability_index
        :type pathway_suitability_index: int, optional
        :param snap_rescale: Enable snap rescale,
            defaults to DEFAULT_VALUES.snap_rescale
        :type snap_rescale: bool, optional
        :param snap_method: Snap method,
            defaults to DEFAULT_VALUES.snap_method
        :type snap_method: int, optional
        :param sieve_enabled: Enable sieve function,
            defaults to DEFAULT_VALUES.sieve_enabled
        :type sieve_enabled: bool, optional
        :param sieve_threshold: Sieve function threshold,
            defaults to DEFAULT_VALUES.sieve_threshold
        :type sieve_threshold: float, optional
        :param sieve_mask_uuid: Layer UUID for sieve mask layer,
            defaults to ''
        :type sieve_mask_uuid: str, optional
        :param mask_layer_uuids: Layer UUID for mask layer, defaults to ''
        :type mask_layer_uuids: str, optional
        :param scenario_uuid: UUID of a scenario, defaults to None
        :type scenario_uuid: str, optional
        :param ncs_with_carbon: Enable output ncs with carbon,
            defaults to DEFAULT_VALUES.ncs_with_carbon
        :type ncs_with_carbon: bool, optional
        :param landuse_project: Enable output landuse project,
            defaults to DEFAULT_VALUES.landuse_project
        :type landuse_project: bool, optional
        :param landuse_normalized: Enable output landuse normalized,
            defaults to DEFAULT_VALUES.landuse_normalized
        :type landuse_normalized: bool, optional
        :param landuse_weighted: Enable output landuse weighted,
            defaults to DEFAULT_VALUES.landuse_weighted
        :type landuse_weighted: bool, optional
        :param highest_position: Enable output highest position,
            defaults to DEFAULT_VALUES.highest_position
        :type highest_position: bool, optional
        :param nodata_value: No data value for raster layers,
            defaults to DEFAULT_VALUES.nodata_value
        :type nodata_value: float, optional
        :param clip_to_studyarea: enable clipping to studyarea layer,
            defaults to False
        :type clip_to_studyarea: bool, optional
        :param studyarea_layer_uuid: Layer UUID for study area layer,
            defaults to ''
        :type studyarea_layer_uuid: str, optional
        :param relative_impact_matrix: Matrix of relative impact values
            between pathways and PWLs, defaults to empty dictionary
        :type relative_impact_matrix: typing.Dict, optional
        :param constant_rasters_uuids: Layer UUIDs for Constant rasters,
            defaults to empty dictionary
        :type constant_rasters_uuids: typing.Dict, optional
        :param pixel_connectivity_enabled: Enable pixel connectivity analysis
            defaults to True
        :type pixel_connectivity_enabled: bool, optional
        """
        self.scenario_name = scenario_name
        self.scenario_desc = scenario_desc
        if scenario_uuid:
            self.scenario_uuid = uuid.UUID(scenario_uuid)
        self.analysis_extent = SpatialExtent(bbox=extent, crs=analysis_crs)
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
        self.nodata_value = nodata_value

        self.clip_to_studyarea = clip_to_studyarea
        self.studyarea_layer_uuid = studyarea_layer_uuid

        self.relative_impact_matrix = relative_impact_matrix
        self.constant_rasters_uuids = constant_rasters_uuids

        self.pixel_connectivity_enabled = pixel_connectivity_enabled

    def get_activity(
        self, activity_uuid: str
    ) -> typing.Union[Activity, None]:
        """Get activity object by its UUID.

        :param activity_uuid: activity UUID
        :type activity_uuid: str
        :return: Activity object or None if not found
        :rtype: typing.Union[Activity, None]
        """
        activity = None
        filtered = [
            act for act in self.analysis_activities if
            str(act.uuid) == activity_uuid
        ]
        if filtered:
            activity = filtered[0]
        return activity

    def get_priority_layers(self) -> typing.List:
        """Get all priority layers.

        :return: List of priority layer dictionary
        :rtype: typing.List
        """
        return self.priority_layers

    def get_priority_layer(self, identifier) -> typing.Dict:
        """Get priority layer dict by its UUID.

        :param identifier: Priority Layer UUID
        :type identifier: str
        :return: Priority Layer dict
        :rtype: typing.Dict
        """
        priority_layer = None
        filtered = [
            f for f in self.priority_layers if f['uuid'] == str(identifier)]
        if filtered:
            priority_layer = filtered[0]
        return priority_layer

    def get_value(self, attr_name: Settings, default=None):
        """Get attribute value by attribute name.

        :param attr_name: Attribute name/config key
        :type attr_name: Settings
        :param default: Default value if not found, defaults to None
        :type default: any, optional
        :return: Attribute value
        :rtype: any
        """
        return getattr(self, attr_name.value, default)

    def to_dict(self):
        """Convert API task config object to dictionary.

        :return: Dictionary of task config
        :rtype: dict
        """
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
            'activity_mask_uuid_layers': self.activity_mask_uuid_layers,
            'total_input_layers': self.total_input_layers,
            'ncs_with_carbon': self.ncs_with_carbon,
            'landuse_project': self.landuse_project,
            'landuse_normalized': self.landuse_normalized,
            'landuse_weighted': self.landuse_weighted,
            'highest_position': self.highest_position,
            'nodata_value': self.nodata_value,
            'clip_to_studyarea': self.clip_to_studyarea,
            'studyarea_path': self.studyarea_path,
            'studyarea_layer_uuid': self.studyarea_layer_uuid,
            'relative_impact_matrix': self.relative_impact_matrix,
            'activity_constant_rasters': self.activity_constant_rasters,
            'pixel_connectivity_enabled': self.pixel_connectivity_enabled
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
                'mask_paths': activity.mask_paths,
                'layer_styles': activity.layer_styles
            }
            for pathway in activity.pathways:
                activity_dict["pathways"].append({
                    'uuid': str(pathway.uuid),
                    'name': pathway.name,
                    'description': pathway.description,
                    'path': pathway.path,
                    'layer_type': pathway.layer_type,
                    'priority_layers': pathway.priority_layers,
                    'type_options': pathway.type_options,
                    'pathway_type': pathway.pathway_type
                })
            input_dict["activities"].append(activity_dict)
        return input_dict

    @classmethod
    def from_dict(cls, data: dict) -> typing.Self:
        """Create APITaskConfig object from dictionary.

        :param data: dictionary from API
        :type data: dict
        :return: APITaskConfig
        :rtype: APITaskConfig
        """
        config = APITaskConfig(
            data.get('scenario_name', ''), data.get('scenario_desc', ''),
            data.get('extent', []), data.get('analysis_crs'), [], [], []
        )
        config.priority_layers = data.get('priority_layers', [])
        config.priority_layer_groups = data.get('priority_layer_groups', [])

        # fetch analysis task configurations
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
        config.nodata_value = data.get(
            'nodata_value', DEFAULT_VALUES.nodata_value
        )
        config.studyarea_layer_uuid = data.get(
            'studyarea_layer_uuid', ''
        )
        config.clip_to_studyarea = data.get(
            'clip_to_studyarea',
            DEFAULT_VALUES.clip_to_studyarea
        )
        config.relative_impact_matrix = data.get(
            'relative_impact_matrix',
            {}
        )
        config.activity_constant_rasters = data.get(
            'activity_constant_rasters',
            {}
        )
        config.pixel_connectivity_enabled = data.get(
            'pixel_connectivity_enabled',
            DEFAULT_VALUES.pixel_connectivity_enabled
        )

        # store dict of <layer_uuid, list of obj identifier>
        config.priority_uuid_layers = {}
        config.pathway_uuid_layers = {}
        config.carbon_uuid_layers = {}
        config.activity_mask_uuid_layers = {}

        # store priority layers
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

        # store activities
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

            # create activity object
            activity_obj = Activity(
                uuid=uuid.UUID(uuid_str) if uuid_str else uuid.uuid4(),
                name=activity.get('name', ''),
                description=activity.get('description', ''),
                path='',
                layer_type=LayerType(activity.get('layer_type', -1)),
                user_defined=activity.get('user_defined', False),
                pathways=[],
                layer_styles=activity.get('layer_styles', {}),
                mask_paths=activity.get('mask_uuids', []),
                constant_rasters=[]
            )

            # create pathways
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
                    priority_layers=pathway.get("priority_layers", []),
                    type_options=pathway.get("type_options", {}),
                    pathway_type=pathway.get('pathway_type')
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

            # Create constant rasters
            for constant_raster in config.activity_constant_rasters.get(
                uuid_str):
                activity_obj.constant_rasters.append(constant_raster)

                layer_uuid_str = constant_raster.get('uuid', None)
                if layer_uuid_str in config.constant_rasters_uuids:
                    config.constant_rasters_uuids[layer_uuid_str].append(
                        str(layer_uuid_str))
                else:
                    config.constant_rasters_uuids[layer_uuid_str] = [
                            str(layer_uuid_str)]


            # create activity mask paths
            mask_uuids = activity.get('mask_uuids', [])
            for mask_uuid in mask_uuids:
                if mask_uuid in config.activity_mask_uuid_layers:
                    config.activity_mask_uuid_layers[mask_uuids].append(
                        str(mask_uuid))
                else:
                    config.activity_mask_uuid_layers[mask_uuid] = [
                        str(mask_uuid)
                    ]
            config.analysis_activities.append(activity_obj)

        config.mask_layers_paths = config.activity_mask_layer_paths

        # create scenario object
        config.scenario = Scenario(
            uuid=config.scenario_uuid,
            name=config.scenario_name,
            description=config.scenario_desc,
            extent=config.analysis_extent,
            activities=config.analysis_activities,
            weighted_activities=[],
            priority_layer_groups=config.priority_layer_groups
        )

        # calculate total input layers
        config.total_input_layers = (
            len(config.pathway_uuid_layers) +
            len(config.priority_uuid_layers) +
            len(config.carbon_uuid_layers) +
            len(config.constant_rasters_uuids)
        )
        if config.snap_layer_uuid:
            config.total_input_layers += 1
        if config.sieve_mask_uuid:
            config.total_input_layers += 1
        config.total_input_layers += len(config.mask_layer_uuids)
        config.total_input_layers += len(config.activity_mask_uuid_layers)
        return config


class WorkerScenarioAnalysisTask(object):
    """Class to run scenario analysis in worker."""

    MIN_UPDATE_PROGRESS_IN_SECONDS = 1

    def __init__(self, task_config: APITaskConfig,
                 scenario_task: ScenarioTask):
        """Initialize WorkerScenarioAnalysisTask class.

        :param task_config: task config from API request
        :type task_config: APITaskConfig
        :param scenario_task: Task request object
        :type scenario_task: ScenarioTask
        """
        self.task_config = task_config
        self.scenario_task = scenario_task
        self.last_update_progress = None
        self.downloaded_layers = {}
        self.downloaded_layer_count = 0
        self.scenario = task_config.scenario
        self.analysis_task = None

    def prepare_run(self):
        """Prepare resources for the task."""
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
        """Initialize input layers required by analysis task.

        :param scenario_path: Base scenario directory
        :type scenario_path: str
        """
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

        # Init constant raster layers
        constant_layer_paths = {}
        constant_layer_uuids = self.task_config.constant_rasters_uuids.keys()
        if constant_layer_uuids:
            constant_layer_uuids_to_download = [
                p_uuid for p_uuid in constant_layer_uuids if
                str(p_uuid) not in self.downloaded_layers
            ]
            constant_layer_paths = self.copy_input_layers_by_uuids(
                None,
                constant_layer_uuids_to_download,
                scenario_path
            )
            self.downloaded_layers.update(constant_layer_paths)
            constant_layer_paths.update({
                key: val for key, val in self.downloaded_layers.items()
                if key in constant_layer_uuids
            })

        # init activity mask layers
        activity_mask_paths = {}
        for mask_layer in self.task_config.activity_mask_uuid_layers:
            layer_uuid = mask_layer
            if layer_uuid not in self.downloaded_layers:
                layer_paths = self.copy_input_layers_by_uuids(
                    None, [layer_uuid], scenario_path
                )
                activity_mask_paths[layer_uuid] = layer_paths[layer_uuid]
                self.downloaded_layers.update(layer_paths)
            else:
                activity_mask_paths[
                    layer_uuid
                ] = self.downloaded_layers[layer_uuid]
        self.task_config.activity_mask_layer_paths = activity_mask_paths

        # Patch/Fix layer_path into priority layers dictionary
        if priority_layer_paths:
            self.patch_layer_path_to_priority_layers(priority_layer_paths)

        # Patch/Fix layer_path into activities
        self.patch_layer_path_to_activities(
            priority_layer_paths,
            pathway_layer_paths,
            activity_mask_paths,
            constant_layer_paths
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

        # init study area layer path
        if self.task_config.studyarea_layer_uuid:
            layer_uuid = self.task_config.studyarea_layer_uuid
            if layer_uuid not in self.downloaded_layers:
                layer_paths = self.copy_input_layers_by_uuids(
                    None, [layer_uuid], scenario_path
                )
                if layer_uuid in layer_paths:
                    self.task_config.studyarea_path = layer_paths[layer_uuid]
                    self.downloaded_layers.update(layer_paths)
            else:
                self.task_config.studyarea_path = self.downloaded_layers[
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
        """Download input layers by UUIDs to scenario directory.

        :param component_type: Layer component type
        :type component_type: InputLayer.ComponentTypes
        :param uuids: List of Layer UUID
        :type uuids: list
        :param scenario_path: scenario base directory
        :type scenario_path: str
        :return: Dictionary of Layer UUID and actual file path
        :rtype: dict
        """
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
        """Patch/Fix layer_path into priority_layers dictionary.

        :param priority_layer_paths: Dictionary of Layer UUID and
            actual file path
        :type priority_layer_paths: dict
        """
        for priority_layer in self.task_config.priority_layers:
            layer_uuid = priority_layer.get('layer_uuid', None)
            if not layer_uuid or layer_uuid not in priority_layer_paths:
                continue
            priority_layer['path'] = priority_layer_paths[layer_uuid]

    def patch_layer_path_to_activities(
            self, priority_layer_paths,
            pathway_layer_paths,
            activity_mask_layer_paths: dict,
            constant_layer_paths: dict):
        """Patch/Fix layer_path into activities.

        :param priority_layer_paths: Dictionary of Layer UUID and
            actual file path for priority layers
        :type priority_layer_paths: dict
        :param pathway_layer_paths: Dictionary of Layer UUID and
            actual file path for ncs_pathways
        :type pathway_layer_paths: dict
        :param carbon_layer_paths: Dictionary of Layer UUID and
            actual file path for carbon layers
        :type carbon_layer_paths: dict
        :param activity_mask_layer_paths: Dictionary of Layer UUID and
            actual file path for mask layers
        :type activity_mask_layer_paths: dict        """
        pw_uuid_mapped = self.transform_uuid_layer_paths(
            self.task_config.pathway_uuid_layers, pathway_layer_paths)
        priority_uuid_mapped = self.transform_uuid_layer_paths(
            self.task_config.priority_uuid_layers, priority_layer_paths
        )
        constant_raster_uuid_mapped = self.transform_uuid_layer_paths(
            self.task_config.constant_rasters_uuids, constant_layer_paths
        )
        # iterate activities
        for activity in self.task_config.analysis_activities:
            for pathway in activity.pathways:
                for priority_layer in pathway.priority_layers:
                    priority_layer_uuid = priority_layer.get('uuid', None)
                    if not priority_layer_uuid:
                        continue
                    if priority_layer_uuid not in priority_uuid_mapped:
                        continue
                    priority_layer['path'] = (
                        priority_uuid_mapped[priority_layer_uuid]
                    )

                pathway_uuid = str(pathway.uuid)
                if pathway_uuid in pw_uuid_mapped:
                    pathway.path = pw_uuid_mapped[pathway_uuid]

                activity.mask_paths = list(activity_mask_layer_paths.values())
                # self.log_message(activity)

            for constant_raster in activity.constant_rasters:
                constant_raster_uuid = str(constant_raster.get("uuid"))
                if constant_raster_uuid in constant_raster_uuid_mapped:
                    constant_raster["path"] = constant_raster_uuid_mapped[
                        constant_raster_uuid
                    ]

        # update reference object
        self.scenario.activities = self.task_config.analysis_activities
        self.analysis_activities = (
            self.task_config.analysis_activities
        )

    def transform_uuid_layer_paths(self, uuid_layers, layer_paths):
        """Create mapping between Object UUID and layer file path.

        This is used to map the layer file path from Layer UUID back to
        the actual objects that are using the layer.

        :param uuid_layers: Dictionary of Layer UUID and List of Object UUID
        :type uuid_layers: dict
        :param layer_paths: Dictionary of Layer UUID and actual file path
        :type layer_paths: dict
        :return: Dictionary of Objet UUID and layer file path
        :rtype: dict
        """
        uuid_mapped = {}
        for layer_uuid, uuid_list in uuid_layers.items():
            if layer_uuid not in layer_paths:
                continue
            for uuid_str in uuid_list:
                uuid_mapped[uuid_str] = layer_paths[layer_uuid]
        return uuid_mapped

    def cancel_task(self, exception=None):
        """Cancel running task

        :param exception: Exception if any, defaults to None
        :type exception: Exception, optional
        """
        self.error = exception
        self.cancel()

    def log_message(self, message: str, name: str = "qgis_cplus",
                    info: bool = True, notify: bool = True):
        """Handle when log is received from running task.

        :param message: Message log
        :type message: str
        :param name: log name, defaults to "qgis_cplus"
        :type name: str, optional
        :param info: True if it is information log, defaults to True
        :type info: bool, optional
        :param notify: Not used in API, defaults to True
        :type notify: bool, optional
        """
        self.scenario_task.add_log(
            message, logging.INFO if info else logging.ERROR)
        level = logging.INFO if info else logging.WARNING
        logger.log(level, message)

    def set_status_message(self, message):
        """Handle when status message is received from running task.

        :param message: Status/Progress Text Message
        :type message: str
        """
        self.status_message = message
        self.scenario_task.progress_text = message
        self.scenario_task.save(update_fields=['progress_text'])

    def set_info_message(self, message, level):
        """Handle when info message is received.

        :param message: Message log
        :type message: str
        :param level: severity level
        :type level: int
        """
        # info_message seems the same with log_message
        self.info_message = message

    def set_custom_progress(self, value):
        """Handle progress value to update task's progress.

        This method will limit the updating to database to
        avoid too many queries.
        :param value: Progress value
        :type value: float
        """
        self.custom_progress = value
        self.scenario_task.progress = value
        # check how to control the frequency of updating progress
        # if too frequent, then the process becomes slower
        should_update_progress = self.should_update_progress()
        if should_update_progress:
            self.last_update_progress = timezone.now()
            self.scenario_task.save(update_fields=['progress'])

    def should_update_progress(self):
        """Check whether should update back to database.

        :return: True if last update time is more than 1s
        :rtype: bool
        """
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
        """Update output layer to object storage.

        :param file_path: output layer file path
        :type file_path: str
        :param scenario_task: ScenarioTask object
        :type scenario_task: ScenarioTask
        :param is_final_output: True if it is the final output layer
        :type is_final_output: bool
        :param group: layer group
        :type group: str
        :param output_meta: Metadata of layer, defaults to None
        :type output_meta: dict, optional
        :return: saved OutputLayer object
        :rtype: OutputLayer
        """
        filename = os.path.basename(file_path)

        # convert to COG if it is Raster type
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

        # create the OutputLayer object
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

        # save the binary file to object storage
        with open(final_output_path, 'rb') as output_file:
            output_layer.file.save(filename, output_file)
        return output_layer

    def upload_scenario_outputs(self):
        """Upload all scenario output layers to object storage."""
        scenario_output_files, total_files = (
            self.scenario_task.get_scenario_output_files()
        )
        status_msg = 'Uploading scenario outputs to storage.'
        self.set_status_message(status_msg)
        self.log_message(status_msg)
        self.log_message(json.dumps(scenario_output_files))
        self.set_custom_progress(0)

        # iterate for each scenario output files
        total_uploaded_files = 0
        for group, files in scenario_output_files.items():
            is_final_output = group == 'final_output'
            if is_final_output:
                output_meta = self.analysis_task.output
                if 'OUTPUT' in output_meta:
                    del output_meta['OUTPUT']
                self.create_and_upload_output_layer(
                    files[0], self.scenario_task,
                    True, None, self.analysis_task.output
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
        """Send email to notify user that analysis task is finished.

        :param is_success: True if task run successfully
        :type is_success: bool
        """
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

            # render message in HTML string
            message = render_to_string(
                'emails/analysis_completed.html',
                {
                    'protocol': 'http' if settings.DEBUG else 'https',
                    'domain': Site.objects.get_current().domain,
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

            # send message
            subject = (
                f'Your analysis of {scenario_name} '
                'has finished successfully' if
                is_success else
                f'Your analysis of {scenario_name} has stopped with errors'
            )
            send_mail(
                subject,
                None,
                settings.DEFAULT_FROM_EMAIL,
                [self.scenario_task.submitted_by.email],
                html_message=message
            )
        except Exception as exc:
            logger.error(f'Unexpected exception occured: {type(exc).__name__} '
                         'when sending email')
            logger.error(exc)
            logger.error(traceback.format_exc())

    def run(self):
        """Run the analysis task."""
        # create task_config object
        analysis_config = TaskConfig(
            self.scenario,
            self.task_config.priority_layers,
            self.scenario.priority_layer_groups,
            self.scenario.activities,
            self.task_config.analysis_activities,
            self.task_config.get_value(
                Settings.SNAPPING_ENABLED, default=False
            ),
            self.task_config.snap_layer,
            self.task_config.mask_layers_paths,
            self.task_config.get_value(
                Settings.RESCALE_VALUES, default=False
            ),
            self.task_config.get_value(Settings.RESAMPLING_METHOD, default=0),
            self.task_config.get_value(
                Settings.PATHWAY_SUITABILITY_INDEX, default=0
            ),
            self.task_config.get_value(
                Settings.CARBON_COEFFICIENT, default=0.0
            ),
            self.task_config.get_value(
                Settings.SIEVE_ENABLED, default=False
            ),
            self.task_config.get_value(
                Settings.SIEVE_THRESHOLD, default=10.0
            ),
            self.task_config.get_value(
                Settings.NCS_WITH_CARBON, default=True
            ),
            self.task_config.get_value(
                Settings.LANDUSE_PROJECT, default=True
            ),
            self.task_config.get_value(
                Settings.LANDUSE_NORMALIZED, default=True
            ),
            self.task_config.get_value(
                Settings.LANDUSE_WEIGHTED, default=True
            ),
            self.task_config.get_value(
                Settings.HIGHEST_POSITION, default=True
            ),
            self.scenario_task.get_resources_path(),
            self.task_config.nodata_value,
            self.task_config.studyarea_path,
            self.task_config.clip_to_studyarea,
            self.task_config.relative_impact_matrix,
            pixel_connectivity_enabled=(
                self.task_config.pixel_connectivity_enabled
            )
        )

        # create analysis task
        self.analysis_task = ScenarioAnalysisTask(analysis_config)

        # setup signals
        self.analysis_task.custom_progress_changed.connect(
            self.set_custom_progress)
        self.analysis_task.status_message_changed.connect(
            self.set_status_message)
        self.analysis_task.info_message_changed.connect(self.set_info_message)
        self.analysis_task.log_received.connect(self.log_message)
        self.analysis_task.task_cancelled.connect(self.cancel_task)

        # call run
        self.analysis_task.run()

    def finished(self, result: bool):
        """Handle when task has been run.

        :param result: True if task run successfully
        :type result: bool
        """
        if result:
            # upload output files
            self.upload_scenario_outputs()
        else:
            self.log_message(
                f"Error from task scenario task {self.error}", info=False)

        # clean directory
        self.scenario_task.clear_resources()

        # update scenario task object
        self.scenario_task.task_on_completed()
        self.scenario_task.updated_detail = json.loads(
            json.dumps(todict(self.scenario), cls=CustomJsonEncoder)
        )
        self.scenario_task.save()

        # send email to the submitter
        self.notify_user(result)
