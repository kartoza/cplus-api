import uuid
from rest_framework import serializers
from drf_yasg import openapi
from cplus_api.models.layer import BaseLayer, InputLayer


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
    if not input_layer.file.storage.exists(input_layer.file.name):
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
            },
            'required': []
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
            },
            'required': []
        }


class ImplementationModelSerializer(BaseLayerSerializer):
    pathways = PathwaySerializer(many=True)
    priority_layers = PriorityLayerSerializer(many=True)

    class Meta:
        swagger_schema_fields = {
            'type': openapi.TYPE_OBJECT,
            'title': 'Implementation Model',
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
            },
            'required': []
        }


class ScenarioInputSerializer(serializers.Serializer):
    scenario_name = serializers.CharField(required=True)
    scenario_desc = serializers.CharField(required=True)
    snapping_enabled = serializers.BooleanField(required=False)
    snap_layer = serializers.CharField(required=False)
    pathway_suitability_index = serializers.IntegerField(required=False)
    carbon_coefficient = serializers.FloatField(required=False)
    snap_rescale = serializers.BooleanField(required=False)
    snap_method = serializers.IntegerField(required=False)
    extent = serializers.ListField(
        child=serializers.FloatField(),
        allow_empty=False,
        min_length=4,
        max_length=4
    )
    priority_layers = PriorityLayerSerializer(many=True)
    priority_layer_groups = PriorityGroupSerializer(many=True)
    implementation_models = ImplementationModelSerializer(many=True)

    class Meta:
        swagger_schema_fields = {
            'type': openapi.TYPE_OBJECT,
            'title': 'Scenario Detail',
            'properties': {
                'scenario_name': openapi.Schema(
                    title='Scenario Name',
                    type=openapi.TYPE_STRING
                ),
                'scenario_desc': openapi.Schema(
                    title='Scenario Description',
                    type=openapi.TYPE_STRING
                ),
                'snapping_enabled': openapi.Schema(
                    title='Is Snapping Enabled',
                    type=openapi.TYPE_BOOLEAN
                ),
                'snap_layer': openapi.Schema(
                    title='Snap layer path',
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
                    title='Snap Method',
                    type=openapi.TYPE_INTEGER
                ),
                'extent': openapi.Schema(
                    title='Analysis Extent',
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
                'implementation_models': openapi.Schema(
                    title='List of implementation model',
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(
                        **ImplementationModelSerializer.Meta.
                        swagger_schema_fields
                    )
                ),
            },
            'required': []
        }
