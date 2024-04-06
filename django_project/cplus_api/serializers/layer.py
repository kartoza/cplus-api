from rest_framework import serializers
from drf_yasg import openapi
from cplus_api.models.layer import BaseLayer, InputLayer


LAYER_SCHEMA_FIELDS = {
    'type': openapi.TYPE_OBJECT,
    'title': 'Layer',
    'properties': {
        'filename': openapi.Schema(
            title='Filename',
            type=openapi.TYPE_STRING
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
            type=openapi.TYPE_STRING
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
    'required': [],
    'example': {
        'filename': 'Final_Alien_Invasive_Plant_priority_norm.tif',
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


class InputLayerSerializer(serializers.ModelSerializer):
    filename = serializers.CharField(source='name')
    created_by = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

    def get_created_by(self, obj: InputLayer):
        return obj.owner.email

    def get_url(self, obj: InputLayer):
        if not obj.file.name:
            return None
        if not obj.file.storage.exists(obj.file.name):
            return None
        return obj.file.url

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
