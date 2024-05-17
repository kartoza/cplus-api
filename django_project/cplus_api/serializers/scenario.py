import uuid
from logging import getLevelName
from rest_framework import serializers
from drf_yasg import openapi
from django.contrib.contenttypes.models import ContentType
from core.models.base_task_request import TaskStatus
from core.models.task_log import TaskLog
from cplus_api.models.layer import BaseLayer, InputLayer
from cplus_api.models.scenario import ScenarioTask


def validate_layer_uuid(value):
    if value == '':
        return
    valid = False
    try:
        uuid.UUID(hex=value)
        valid = True
    except ValueError:
        valid = False
    if not valid:
        raise serializers.ValidationError(f'{value} is not a valid UUID!')
    # check input layer exists and ready
    input_layer = InputLayer.objects.filter(
        uuid=value
    ).first()
    if not input_layer:
        raise serializers.ValidationError(
            f'Invalid input layer object {value}!')
    if not input_layer.is_available():
        raise serializers.ValidationError(
            f'Missing input layer {value} file!')


class BaseLayerSerializer(serializers.Serializer):
    uuid = serializers.UUIDField()
    name = serializers.CharField()
    description = serializers.CharField()
    layer_uuid = serializers.CharField(
        required=False, allow_blank=True,
        validators=[validate_layer_uuid])
    layer_type = serializers.IntegerField(
        default=InputLayer.LayerTypes.RASTER
    )
    user_defined = serializers.BooleanField(required=False)

    class Meta:
        properties_fields = {
            'uuid': openapi.Schema(
                title='Client Layer UUID',
                type=openapi.TYPE_STRING
            ),
            'name': openapi.Schema(
                title='name',
                type=openapi.TYPE_STRING
            ),
            'description': openapi.Schema(
                title='description',
                type=openapi.TYPE_STRING
            ),
            'layer_uuid': openapi.Schema(
                title='Layer UUID',
                type=openapi.TYPE_STRING
            ),
            'layer_type': openapi.Schema(
                title='Layer Type',
                type=openapi.TYPE_INTEGER,
                enum=[
                    BaseLayer.LayerTypes.RASTER,
                    BaseLayer.LayerTypes.VECTOR,
                    BaseLayer.LayerTypes.UNDEFINED
                ],
            ),
            'user_defined': openapi.Schema(
                title='User Defined',
                type=openapi.TYPE_BOOLEAN
            ),
        }


class GroupSerializer(serializers.Serializer):
    uuid = serializers.UUIDField()
    name = serializers.CharField()
    value = serializers.IntegerField(default=0)

    class Meta:
        swagger_schema_fields = {
            'type': openapi.TYPE_OBJECT,
            'title': 'Group',
            'properties': {
                'uuid': openapi.Schema(
                    title='Group UUID',
                    type=openapi.TYPE_STRING
                ),
                'name': openapi.Schema(
                    title='Group Name',
                    type=openapi.TYPE_STRING
                ),
                'value': openapi.Schema(
                    title='Value',
                    type=openapi.TYPE_INTEGER
                ),
            },
            'required': ['uuid', 'name', 'value'],
            'example': {
                'uuid': '8c4582ab-15b1-4ed0-b8e4-00640ec10a65',
                'name': 'Climate Resilience',
                'value': 0
            }
        }


class PriorityGroupSerializer(serializers.Serializer):
    name = serializers.CharField()
    value = serializers.IntegerField()
    layers = serializers.ListField(
        child=serializers.CharField()
    )

    class Meta:
        swagger_schema_fields = {
            'type': openapi.TYPE_OBJECT,
            'title': 'Priority Group',
            'properties': {
                'name': openapi.Schema(
                    title='Group Name',
                    type=openapi.TYPE_STRING
                ),
                'value': openapi.Schema(
                    title='Value',
                    type=openapi.TYPE_INTEGER
                ),
                'layers': openapi.Schema(
                    title='List of layers',
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_STRING)
                ),
            },
            'required': ['name', 'value', 'layers'],
            'example': {
                'name': 'Climate Resilience',
                'value': 0,
                'layers': []
            }
        }


class PriorityLayerSerializer(BaseLayerSerializer):
    selected = serializers.BooleanField()
    groups = GroupSerializer(many=True)

    class Meta:
        swagger_schema_fields = {
            'type': openapi.TYPE_OBJECT,
            'title': 'Priority Layer',
            'properties': {
                **BaseLayerSerializer.Meta.properties_fields,
                'selected': openapi.Schema(
                    title='selected',
                    type=openapi.TYPE_BOOLEAN
                ),
                'groups': openapi.Schema(
                    title='List of groups',
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(
                        **GroupSerializer.Meta.swagger_schema_fields)
                ),
            }
        }


class PathwaySerializer(BaseLayerSerializer):
    carbon_uuids = serializers.ListField(
        child=serializers.UUIDField()
    )

    class Meta:
        swagger_schema_fields = {
            'type': openapi.TYPE_OBJECT,
            'title': 'Pathway',
            'properties': {
                **BaseLayerSerializer.Meta.properties_fields,
                'carbon_uuids': openapi.Schema(
                    title='List of carbon layer UUID',
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(
                        type=openapi.TYPE_STRING
                    )
                ),
            }
        }


class ActivitySerializer(BaseLayerSerializer):
    pathways = PathwaySerializer(many=True)
    priority_layers = PriorityLayerSerializer(many=True)

    class Meta:
        swagger_schema_fields = {
            'type': openapi.TYPE_OBJECT,
            'title': 'Activity',
            'properties': {
                **BaseLayerSerializer.Meta.properties_fields,
                'pathways': openapi.Schema(
                    title='List of pathway',
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(
                        **PathwaySerializer.Meta.swagger_schema_fields)
                ),
                'priority_layers': openapi.Schema(
                    title='List of priority layer',
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(
                        **PriorityLayerSerializer.Meta.swagger_schema_fields)
                ),
            }
        }


class ScenarioInputSerializer(serializers.Serializer):
    scenario_name = serializers.CharField(required=True)
    scenario_desc = serializers.CharField(required=True)
    snapping_enabled = serializers.BooleanField(required=False)
    snap_layer = serializers.CharField(required=False, allow_blank=True)
    snap_layer_uuid = serializers.CharField(
        required=False, validators=[validate_layer_uuid], allow_blank=True
    )
    pathway_suitability_index = serializers.IntegerField(required=False)
    carbon_coefficient = serializers.FloatField(required=False)
    snap_rescale = serializers.BooleanField(required=False)
    snap_method = serializers.IntegerField(required=False)
    sieve_enabled = serializers.BooleanField(required=False)
    sieve_threshold = serializers.FloatField(required=False)
    sieve_mask_path = serializers.CharField(required=False, allow_blank=True)
    sieve_mask_uuid = serializers.CharField(
        required=False, validators=[validate_layer_uuid], allow_blank=True
    )
    mask_path = serializers.CharField(required=False, allow_blank=True)
    mask_layer_uuids = serializers.ListField(
        required=False,
        child=serializers.CharField(
            required=False, validators=[validate_layer_uuid]
        )
    )
    extent = serializers.ListField(
        child=serializers.FloatField(),
        allow_empty=False,
        min_length=4,
        max_length=4
    )
    priority_layers = PriorityLayerSerializer(many=True)
    priority_layer_groups = PriorityGroupSerializer(many=True)
    activities = ActivitySerializer(many=True)

    class Meta:
        swagger_schema_fields = {
            'type': openapi.TYPE_OBJECT,
            'title': 'Scenario Detail',
            'properties': {
                'scenario_name': openapi.Schema(
                    title='Scenario name',
                    type=openapi.TYPE_STRING
                ),
                'scenario_desc': openapi.Schema(
                    title='Scenario description',
                    type=openapi.TYPE_STRING
                ),
                'snapping_enabled': openapi.Schema(
                    title='Is snapping enabled',
                    type=openapi.TYPE_BOOLEAN
                ),
                'snap_layer': openapi.Schema(
                    title='Snap layer Path',
                    type=openapi.TYPE_STRING
                ),
                'snap_layer_uuid': openapi.Schema(
                    title='Snap layer UUID',
                    type=openapi.TYPE_STRING
                ),
                'pathway_suitability_index': openapi.Schema(
                    title='Pathway suitability index',
                    type=openapi.TYPE_INTEGER
                ),
                'carbon_coefficient': openapi.Schema(
                    title='Carbon coefficient',
                    type=openapi.TYPE_NUMBER
                ),
                'snap_rescale': openapi.Schema(
                    title='Is snap rescale',
                    type=openapi.TYPE_BOOLEAN
                ),
                'snap_method': openapi.Schema(
                    title='Snap method',
                    type=openapi.TYPE_INTEGER
                ),
                'sieve_enabled': openapi.Schema(
                    title='Is sieve function enabled',
                    type=openapi.TYPE_BOOLEAN
                ),
                'sieve_threshold': openapi.Schema(
                    title='Sieve function threshold',
                    type=openapi.TYPE_NUMBER
                ),
                'sieve_mask_path': openapi.Schema(
                    title='Sieve mask layer path',
                    type=openapi.TYPE_STRING
                ),
                'sieve_mask_uuid': openapi.Schema(
                    title='Sieve mask layer UUID',
                    type=openapi.TYPE_STRING
                ),
                'mask_path': openapi.Schema(
                    title='Mask layer path',
                    type=openapi.TYPE_STRING
                ),
                'mask_layer_uuids': openapi.Schema(
                    title='Mask layer UUIDs',
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_STRING),
                ),
                'extent': openapi.Schema(
                    title='Analysis extent',
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_NUMBER),
                    minItems=4,
                    maxItems=4
                ),
                'priority_layers': openapi.Schema(
                    title='List of priority layer',
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(
                        **PriorityLayerSerializer.Meta.
                        swagger_schema_fields
                    )
                ),
                'priority_layer_groups': openapi.Schema(
                    title='List of priority layer group',
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(
                        **PriorityGroupSerializer.Meta.
                        swagger_schema_fields
                    )
                ),
                'activities': openapi.Schema(
                    title='List of activity',
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(
                        **ActivitySerializer.Meta.
                        swagger_schema_fields
                    )
                ),
            }
        }


class ScenarioTaskStatusSerializer(serializers.ModelSerializer):
    scenario_name = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    logs = serializers.SerializerMethodField()

    def get_created_by(self, obj: ScenarioTask):
        return obj.submitted_by.email

    def get_scenario_name(self, obj: ScenarioTask):
        if not obj.detail:
            return ''
        return (
            obj.detail['scenario_name'] if
            'scenario_name' in obj.detail else ''
        )

    def get_logs(self, obj: ScenarioTask):
        scenario_task_ct = ContentType.objects.get(
            app_label="cplus_api", model="scenariotask")
        return TaskLog.objects.filter(
            content_type=scenario_task_ct,
            object_id=obj.pk
        ).order_by('date_time').values_list('log', flat=True)

    class Meta:
        swagger_schema_fields = {
            'type': openapi.TYPE_OBJECT,
            'title': 'Scenario Task Status',
            'properties': {
                'uuid': openapi.Schema(
                    title='Scenario UUID',
                    type=openapi.TYPE_STRING
                ),
                'task_id': openapi.Schema(
                    title='Task ID',
                    type=openapi.TYPE_STRING
                ),
                'plugin_version': openapi.Schema(
                    title='Plugin version',
                    type=openapi.TYPE_STRING
                ),
                'scenario_name': openapi.Schema(
                    title='Scenario Name',
                    type=openapi.TYPE_STRING
                ),
                'status': openapi.Schema(
                    title='Scenario Status',
                    type=openapi.TYPE_STRING,
                    enum=[
                        TaskStatus.PENDING,
                        TaskStatus.QUEUED,
                        TaskStatus.RUNNING,
                        TaskStatus.STOPPED,
                        TaskStatus.COMPLETED,
                        TaskStatus.CANCELLED,
                        TaskStatus.INVALIDATED
                    ]
                ),
                'submitted_on': openapi.Schema(
                    title='Created Date Time',
                    type=openapi.TYPE_STRING
                ),
                'created_by': openapi.Schema(
                    title='Owner Email',
                    type=openapi.TYPE_STRING
                ),
                'started_at': openapi.Schema(
                    title='Started Date Time',
                    type=openapi.TYPE_STRING
                ),
                'finished_at': openapi.Schema(
                    title='Finished Date Time',
                    type=openapi.TYPE_STRING
                ),
                'errors': openapi.Schema(
                    title='Errors',
                    type=openapi.TYPE_STRING
                ),
                'progress': openapi.Schema(
                    title='Percentage of the progress',
                    type=openapi.TYPE_NUMBER
                ),
                'progress_text': openapi.Schema(
                    title='Progress Description',
                    type=openapi.TYPE_STRING
                ),
                'logs': openapi.Schema(
                    title='Logs',
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_STRING),
                ),
            },
            'example': {
                'uuid': '8c4582ab-15b1-4ed0-b8e4-00640ec10a65',
                'task_id': '3e0c7dff-51f2-48c5-a316-15d9ca2407cb',
                'plugin_version': '1.0.0',
                'scenario_name': 'Scenario A',
                'status': 'Queued',
                'submitted_on': '2022-08-15T08:09:15.049806Z',
                'created_by': 'admin@admin.com',
                'started_at': '2022-08-15T08:09:15.049806Z',
                'finished_at': '2022-08-15T09:09:15.049806Z',
                'errors': None,
                'progress': 70,
                'progress_text': 'Processing ABC',
                'logs': []
            }
        }
        model = ScenarioTask
        fields = [
            'uuid', 'task_id', 'plugin_version',
            'scenario_name', 'status', 'submitted_on',
            'created_by', 'started_at', 'finished_at',
            'errors', 'progress', 'progress_text',
            'logs'
        ]


class ScenarioTaskLogSerializer(serializers.ModelSerializer):
    severity = serializers.SerializerMethodField()

    def get_severity(self, obj: TaskLog):
        return getLevelName(obj.level)

    class Meta:
        swagger_schema_fields = {
            'type': openapi.TYPE_OBJECT,
            'title': 'Scenario Log',
            'properties': {
                'date_time': openapi.Schema(
                    title='Log Date Time',
                    type=openapi.TYPE_STRING
                ),
                'severity': openapi.Schema(
                    title='Log Severity',
                    type=openapi.TYPE_STRING
                ),
                'log': openapi.Schema(
                    title='Log text',
                    type=openapi.TYPE_STRING
                ),
            },
            'example': {
                'date_time': '2022-08-15T09:09:15.049806Z',
                'severity': 'INFO',
                'log': 'Processing ABC is finished'
            }
        }
        model = TaskLog
        fields = [
            'date_time', 'severity', 'log'
        ]


class ScenarioTaskLogListSerializer(serializers.ListSerializer):
    child = ScenarioTaskLogSerializer()


class PaginatedScenarioTaskStatusSerializer(serializers.Serializer):
    page = serializers.IntegerField()
    total_page = serializers.IntegerField()
    page_size = serializers.IntegerField()
    results = ScenarioTaskStatusSerializer(many=True)

    class Meta:
        swagger_schema_fields = {
            'type': openapi.TYPE_OBJECT,
            'title': 'Scenario History List',
            'properties': {
                'page': openapi.Schema(
                    title='Page Number',
                    type=openapi.TYPE_INTEGER
                ),
                'total_page': openapi.Schema(
                    title='Total Page',
                    type=openapi.TYPE_INTEGER
                ),
                'page_size': openapi.Schema(
                    title='Total item in 1 page',
                    type=openapi.TYPE_INTEGER
                ),
                'results': openapi.Schema(
                    title='Results',
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(
                        **ScenarioTaskStatusSerializer.
                        Meta.swagger_schema_fields
                    ),
                )
            }
        }


class ScenarioDetailSerializer(ScenarioTaskStatusSerializer):
    class Meta:
        model = ScenarioTask
        fields = [
            'uuid', 'task_id', 'plugin_version',
            'scenario_name', 'status', 'submitted_on',
            'created_by', 'started_at', 'finished_at',
            'errors', 'progress', 'progress_text',
            'detail', 'updated_detail'
        ]
        swagger_schema_fields = {
            'type': openapi.TYPE_OBJECT,
            'title': 'Scenario Task Detail',
            'properties': {
                **ScenarioTaskStatusSerializer.Meta.
                swagger_schema_fields['properties'],
                'detail': {
                    **ScenarioInputSerializer.Meta.swagger_schema_fields
                }
            }
        }
