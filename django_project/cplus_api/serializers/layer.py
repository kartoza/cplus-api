from rest_framework import serializers
from drf_yasg import openapi
from django.conf import settings
from cplus_api.models.layer import BaseLayer, InputLayer, OutputLayer
from cplus_api.utils.api_helper import build_minio_absolute_url


LAYER_SCHEMA_FIELDS = {
    'type': openapi.TYPE_OBJECT,
    'title': 'Layer',
    'properties': {
        'filename': openapi.Schema(
            title='Filename',
            type=openapi.TYPE_STRING
        ),
        'size': openapi.Schema(
            title='Layer File Size',
            type=openapi.TYPE_INTEGER
        ),
        'uuid': openapi.Schema(
            title='Layer UUID',
            type=openapi.TYPE_STRING
        ),
        'created_on': openapi.Schema(
            title='Created Date Time',
            type=openapi.TYPE_STRING
        ),
        'created_by': openapi.Schema(
            title='Owner email',
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
        'component_type': openapi.Schema(
            title='Component Type',
            type=openapi.TYPE_STRING,
            enum=[
                InputLayer.ComponentTypes.NCS_CARBON,
                InputLayer.ComponentTypes.NCS_PATHWAY,
                InputLayer.ComponentTypes.PRIORITY_LAYER
            ],
        ),
        'privacy_type': openapi.Schema(
            title='Privacy Type',
            type=openapi.TYPE_STRING,
            enum=[
                InputLayer.PrivacyTypes.COMMON,
                InputLayer.PrivacyTypes.INTERNAL,
                InputLayer.PrivacyTypes.PRIVATE
            ]
        ),
        'url': openapi.Schema(
            title='Layer Download URL',
            type=openapi.TYPE_STRING
        ),
        'client_id': openapi.Schema(
            title='ID given by client',
            type=openapi.TYPE_STRING,
        ),
    },
    'required': [
        'filename', 'size', 'uuid', 'layer_type',
        'component_type', 'privacy_type'
    ],
    'example': {
        'filename': 'Final_Alien_Invasive_Plant_priority_norm.tif',
        'size': 100000000,
        'uuid': '8c4582ab-15b1-4ed0-b8e4-00640ec10a65',
        'layer_type': 0,
        'component_type': 'ncs_pathway',
        'privacy_type': 'common',
        'created_by': 'admin@admin.com',
        'created_on': '2022-08-15T08:09:15.049806Z',
        'url': '',
        'client_id': ''
    }
}


OUTPUT_LAYER_SCHEMA_FIELDS = {
    'type': openapi.TYPE_OBJECT,
    'title': 'Scenario Output',
    'properties': {
        'filename': openapi.Schema(
            title='Filename',
            type=openapi.TYPE_STRING
        ),
        'size': openapi.Schema(
            title='Layer File Size',
            type=openapi.TYPE_INTEGER
        ),
        'uuid': openapi.Schema(
            title='Output Layer UUID',
            type=openapi.TYPE_STRING
        ),
        'created_on': openapi.Schema(
            title='Created Date Time',
            type=openapi.TYPE_STRING
        ),
        'created_by': openapi.Schema(
            title='Owner email',
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
        'url': openapi.Schema(
            title='Layer Download URL',
            type=openapi.TYPE_STRING
        ),
        'is_final_output': openapi.Schema(
            title='Is Final Output Layer',
            type=openapi.TYPE_BOOLEAN,
        ),
        'group': openapi.Schema(
            title='Layer Output Group',
            type=openapi.TYPE_STRING,
            enum=[
                "activities",
                "normalized_ims",
                "normalized_pathways",
                "weighted_ims"
            ],
        ),
        'output_meta': openapi.Schema(
            title='Output Metadata',
            type=openapi.TYPE_OBJECT,
        ),
    },
    'required': [
        'filename', 'size', 'uuid', 'layer_type'
    ],
    'example': {
        'filename': 'Final_Alien_Invasive_Plant_priority_norm.tif',
        'size': 100000000,
        'uuid': '8c4582ab-15b1-4ed0-b8e4-00640ec10a65',
        'layer_type': 0,
        'created_by': 'admin@admin.com',
        'created_on': '2022-08-15T08:09:15.049806Z',
        'url': '',
        'is_final_output': False,
        'group': 'weighted_ims'
    }
}


class InputLayerSerializer(serializers.ModelSerializer):
    filename = serializers.CharField(source='name')
    created_by = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

    def get_created_by(self, obj: InputLayer):
        return obj.owner.email

    def get_url(self, obj: InputLayer):
        if not obj.file.name:
            return None
        if not obj.is_available():
            return None
        return build_minio_absolute_url(obj.file.url)

    class Meta:
        swagger_schema_fields = LAYER_SCHEMA_FIELDS
        model = InputLayer
        fields = [
            'uuid', 'filename', 'created_on',
            'created_by', 'layer_type', 'size',
            'url', 'component_type', 'privacy_type',
            'client_id'
        ]


class PaginatedInputLayerSerializer(serializers.Serializer):
    page = serializers.IntegerField()
    total_page = serializers.IntegerField()
    page_size = serializers.IntegerField()
    results = InputLayerSerializer(many=True)

    class Meta:
        swagger_schema_fields = {
            'type': openapi.TYPE_OBJECT,
            'title': 'Layer List',
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
                    items=openapi.Items(**LAYER_SCHEMA_FIELDS),
                )
            }
        }


class UploadLayerSerializer(serializers.Serializer):
    layer_type = serializers.IntegerField()
    component_type = serializers.CharField()
    privacy_type = serializers.CharField()
    client_id = serializers.CharField(required=False)
    uuid = serializers.CharField(required=False)
    name = serializers.CharField(required=True)
    size = serializers.IntegerField(required=True, min_value=1)
    number_of_parts = serializers.IntegerField(required=False, default=0)

    class Meta:
        swagger_schema_fields = {
            'type': openapi.TYPE_OBJECT,
            'title': 'Layer Upload',
            'properties': {
                'layer_type': openapi.Schema(
                    title=(
                        'Layer Type - 0 (Raster), 1 (Vector), -1 (Undefined)'
                    ),
                    type=openapi.TYPE_INTEGER,
                    enum=[
                        BaseLayer.LayerTypes.RASTER,
                        BaseLayer.LayerTypes.VECTOR,
                        BaseLayer.LayerTypes.UNDEFINED
                    ],
                    default=BaseLayer.LayerTypes.RASTER
                ),
                'component_type': openapi.Schema(
                    title='Component Type',
                    type=openapi.TYPE_STRING,
                    enum=[
                        InputLayer.ComponentTypes.NCS_CARBON,
                        InputLayer.ComponentTypes.NCS_PATHWAY,
                        InputLayer.ComponentTypes.PRIORITY_LAYER,
                    ]
                ),
                'privacy_type': openapi.Schema(
                    title='Privacy Type',
                    type=openapi.TYPE_STRING,
                    enum=[
                        InputLayer.PrivacyTypes.PRIVATE,
                        InputLayer.PrivacyTypes.INTERNAL,
                        InputLayer.PrivacyTypes.COMMON,
                    ],
                    default=InputLayer.PrivacyTypes.PRIVATE
                ),
                'client_id': openapi.Schema(
                    title='ID given by the client',
                    type=openapi.TYPE_STRING
                ),
                'uuid': openapi.Schema(
                    title='Layer UUID for updating existing layer',
                    type=openapi.TYPE_STRING
                ),
                'name': openapi.Schema(
                    title='Layer file name',
                    type=openapi.TYPE_STRING
                ),
                'size': openapi.Schema(
                    title='Layer file size',
                    type=openapi.TYPE_INTEGER
                ),
                'number_of_parts': openapi.Schema(
                    title='Number of parts for multipart upload.',
                    type=openapi.TYPE_INTEGER,
                    default=0
                )
            },
            'required': [
                'layer_type', 'component_type', 'privacy_type',
                'name', 'size'
            ]
        }


class UploadMetadataItem(serializers.Serializer):
    etag = serializers.CharField()
    part_number = serializers.IntegerField()

    class Meta:
        swagger_schema_fields = {
            'type': openapi.TYPE_OBJECT,
            'title': 'Upload metadata item',
            'properties': {
                'etag': openapi.Schema(
                    title='Etag value from S3 Upload Response',
                    type=openapi.TYPE_STRING
                ),
                'part_number': openapi.Schema(
                    title='Part number',
                    type=openapi.TYPE_INTEGER
                )
            },
            'required': ['etag', 'part_number'],
            'example': {
                'etag': '8d242daa57a3ea8d439a71c68038b373',
                'part_number': 1
            }
        }


class FinishUploadLayerSerializer(serializers.Serializer):
    multipart_upload_id = serializers.CharField(required=False)
    items = UploadMetadataItem(many=True, required=False)

    class Meta:
        swagger_schema_fields = {
            'type': openapi.TYPE_OBJECT,
            'title': 'Upload Layer Item',
            'properties': {
                'multipart_upload_id': openapi.Schema(
                    title='Upload Id for multipart upload',
                    type=openapi.TYPE_STRING
                ),
                'items': openapi.Schema(
                    title='List of upload metadata item',
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(
                        **UploadMetadataItem.Meta.swagger_schema_fields
                    )
                ),
            }
        }


class OutputLayerSerializer(serializers.ModelSerializer):
    DEFAULT_GROUP_IN_OUTPUT_URL = ['weighted_activities']
    filename = serializers.CharField(source='name')
    created_by = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

    def check_generate_all_outputs(self, obj: OutputLayer):
        is_fetch_all = self.context.get('is_fetch_all', False)
        if is_fetch_all:
            return True
        if (
            not obj.is_final_output and
            obj.group not in self.DEFAULT_GROUP_IN_OUTPUT_URL
        ):
            return False
        return True

    def get_created_by(self, obj: OutputLayer):
        return obj.owner.email

    def get_url(self, obj: OutputLayer):
        if not self.check_generate_all_outputs(obj):
            return None
        if not obj.file.name:
            return None
        if not obj.file.storage.exists(obj.file.name):
            return None
        if settings.DEBUG:
            return build_minio_absolute_url(obj.file.url)
        return obj.file.url

    class Meta:
        swagger_schema_fields = OUTPUT_LAYER_SCHEMA_FIELDS
        model = OutputLayer
        fields = [
            'uuid', 'filename', 'created_on',
            'created_by', 'layer_type', 'size',
            'url', 'is_final_output', 'group',
            'output_meta'
        ]


class PaginatedOutputLayerSerializer(serializers.Serializer):
    page = serializers.IntegerField()
    total_page = serializers.IntegerField()
    page_size = serializers.IntegerField()
    results = OutputLayerSerializer(many=True)

    class Meta:
        swagger_schema_fields = {
            'type': openapi.TYPE_OBJECT,
            'title': 'Output Layer List',
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
                    items=openapi.Items(**OUTPUT_LAYER_SCHEMA_FIELDS),
                )
            }
        }


class OutputLayerListSerializer(serializers.ListSerializer):
    child = OutputLayerSerializer()
