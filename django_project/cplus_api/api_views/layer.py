import math
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from cplus_api.models.layer import BaseLayer, InputLayer
from cplus_api.serializers.layer import (
    InputLayerSerializer,
    PaginatedInputLayerSerializer
)
from cplus_api.serializers.common import (
    APIErrorSerializer,
    NoContentSerializer
)
from cplus_api.utils.api_helper import (
    get_page_size,
    LAYER_API_TAG,
    PARAM_LAYER_UUID_IN_PATH
)


def is_internal_user(user):
    # TODO: check if user has internal user role
    return True


class LayerList(APIView):
    """API to return available layers."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='layer-list',
        tags=[LAYER_API_TAG],
        responses={
            200: PaginatedInputLayerSerializer,
            400: APIErrorSerializer,
            404: APIErrorSerializer
        }
    )
    def get(self, request, *args, **kwargs):
        page = int(request.GET.get('page', '1'))
        page_size = get_page_size(request)
        layers = InputLayer.objects.filter(
            privacy_type=InputLayer.PrivacyTypes.COMMON
        ).order_by('name')
        if is_internal_user(request.user):
            internal_layers = InputLayer.objects.filter(
                privacy_type=InputLayer.PrivacyTypes.INTERNAL
            ).order_by('name')
            layers = layers.union(internal_layers)
        private_layers = InputLayer.objects.filter(
            privacy_type=InputLayer.PrivacyTypes.PRIVATE,
            owner=request.user
        ).order_by('name')
        layers = layers.union(private_layers)
        layers = layers.order_by('name')
        # set pagination
        paginator = Paginator(layers, page_size)
        total_page = math.ceil(paginator.count / page_size)
        if page > total_page:
            output = []
        else:
            paginated_entities = paginator.get_page(page)
            output = (
                InputLayerSerializer(
                    paginated_entities,
                    many=True
                ).data
            )
        return Response(status=200, data={
            'page': page,
            'total_page': total_page,
            'page_size': page_size,
            'results': output
        })


class LayerUpload(APIView):
    """API to upload layer file."""
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser,)
    layer_type_param = openapi.Parameter(
        'layer_type', openapi.IN_FORM,
        description=(
            'Layer Type: 0 (Raster), 1 (Vector), -1 (Undefined)'
        ),
        type=openapi.TYPE_INTEGER,
        enum=[
            BaseLayer.LayerTypes.RASTER,
            BaseLayer.LayerTypes.VECTOR,
            BaseLayer.LayerTypes.UNDEFINED
        ],
        default=BaseLayer.LayerTypes.RASTER,
        required=True
    )
    component_type_param = openapi.Parameter(
        'component_type', openapi.IN_FORM,
        description=(
            'Component Type'
        ),
        type=openapi.TYPE_STRING,
        enum=[
            InputLayer.ComponentTypes.NCS_CARBON,
            InputLayer.ComponentTypes.NCS_PATHWAY,
            InputLayer.ComponentTypes.PRIORITY_LAYER,
        ],
        required=True
    )
    privacy_type_param = openapi.Parameter(
        'privacy_type', openapi.IN_FORM,
        description=(
            'Privacy Type'
        ),
        type=openapi.TYPE_STRING,
        enum=[
            InputLayer.PrivacyTypes.PRIVATE,
            InputLayer.PrivacyTypes.INTERNAL,
            InputLayer.PrivacyTypes.COMMON,
        ],
        default=InputLayer.PrivacyTypes.PRIVATE,
        required=True
    )
    client_id_param = openapi.Parameter(
        'client_id', openapi.IN_FORM,
        description=(
            'ID given by the client'
        ),
        type=openapi.TYPE_STRING,
        required=False
    )
    layer_uuid_param = openapi.Parameter(
        'uuid', openapi.IN_FORM,
        description=(
            'Layer UUID for updating existing layer file'
        ),
        type=openapi.TYPE_STRING,
        required=False
    )
    layer_file_param = openapi.Parameter(
        'file', openapi.IN_FORM,
        description=(
            'Raster layer file'
        ),
        type=openapi.TYPE_FILE,
        required=True
    )

    @swagger_auto_schema(
        operation_id='layer-upload',
        tags=[LAYER_API_TAG],
        manual_parameters=[
            layer_type_param,
            component_type_param,
            privacy_type_param,
            client_id_param,
            layer_uuid_param,
            layer_file_param
        ],
        responses={
            201: openapi.Schema(
                description=(
                    'Success'
                ),
                type=openapi.TYPE_OBJECT,
                properties={
                    'uuid': openapi.Schema(
                        title='Layer UUID',
                        type=openapi.TYPE_STRING
                    )
                },
                example={
                    'uuid': '8c4582ab-15b1-4ed0-b8e4-00640ec10a65'
                }
            ),
            400: APIErrorSerializer,
            404: APIErrorSerializer
        }
    )
    def post(self, request, format=None):
        file_obj = request.FILES['file']
        filename = file_obj.name
        filesize = file_obj.size
        # TODO: validations
        # - types, able to upload internal/common
        # - file type, max size (?)
        layer_type = request.data.get(
            'layer_type', BaseLayer.LayerTypes.RASTER)
        component_type = request.data.get('component_type', None)
        privacy_type = request.data.get('privacy_type', 'private')
        client_id = request.data.get('client_id', '')
        # for update
        layer_uuid = request.data.get('uuid', '')
        input_layer: InputLayer = None
        if layer_uuid:
            # TODO: update validation: owner/superadmin
            input_layer = get_object_or_404(
                InputLayer, uuid=layer_uuid)
            input_layer.name = filename
            input_layer.created_on = timezone.now()
            input_layer.owner = request.user
            input_layer.layer_type = layer_type
            input_layer.size = filesize
            input_layer.component_type = component_type
            input_layer.privacy_type = privacy_type
            input_layer.client_id = client_id
        else:
            input_layer = InputLayer.objects.create(
                name=filename,
                created_on=timezone.now(),
                owner=request.user,
                layer_type=layer_type,
                size=filesize,
                component_type=component_type,
                privacy_type=privacy_type,
                client_id=client_id
            )
        input_layer.file = file_obj
        input_layer.save()
        return Response(status=201, data={
            'uuid': str(input_layer.uuid)
        })


class LayerDetail(APIView):
    """APIs to fetch and remove layer file."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='layer-detail',
        operation_description='API to fetch layer detail.',
        tags=[LAYER_API_TAG],
        manual_parameters=[PARAM_LAYER_UUID_IN_PATH],
        responses={
            200: InputLayerSerializer,
            400: APIErrorSerializer,
            404: APIErrorSerializer
        }
    )
    def get(self, request, *args, **kwargs):
        # TODO: validation if user can retrieve input layer
        layer_uuid = kwargs.get('layer_uuid')
        input_layer = get_object_or_404(
            InputLayer, uuid=layer_uuid)
        return Response(
            status=200, data=InputLayerSerializer(input_layer).data)

    @swagger_auto_schema(
        operation_id='layer-remove',
        operation_description='API to remove layer.',
        tags=[LAYER_API_TAG],
        manual_parameters=[PARAM_LAYER_UUID_IN_PATH],
        responses={
            204: NoContentSerializer,
            400: APIErrorSerializer,
            404: APIErrorSerializer
        }
    )
    def delete(self, request, *args, **kwargs):
        # TODO: validation if user can delete input layer
        layer_uuid = kwargs.get('layer_uuid')
        input_layer = get_object_or_404(
            InputLayer, uuid=layer_uuid)
        input_layer.delete()
        return Response(status=204)
