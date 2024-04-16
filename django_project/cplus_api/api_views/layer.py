import math
import os
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from cplus_api.models.layer import (
    BaseLayer, InputLayer, input_layer_dir_path,
    select_input_layer_storage
)
from cplus_api.serializers.layer import (
    InputLayerSerializer,
    PaginatedInputLayerSerializer,
    UploadLayerSerializer
)
from cplus_api.serializers.common import (
    APIErrorSerializer,
    NoContentSerializer
)
from cplus_api.utils.api_helper import (
    get_page_size,
    LAYER_API_TAG,
    PARAM_LAYER_UUID_IN_PATH,
    get_presigned_url,
    convert_size
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


class BaseLayerUpload(APIView):
    permission_classes = [IsAuthenticated]

    def validate_upload_access(self, privacy_type, user,
                               is_update = False, existing_layer = None):
        is_valid = False
        if user.is_superuser:
            is_valid = True
        if privacy_type == InputLayer.PrivacyTypes.PRIVATE:
            if is_update:
                is_valid = existing_layer.owner == user
            else:
                is_valid = True
        elif privacy_type == InputLayer.PrivacyTypes.INTERNAL:
            is_valid = is_internal_user(user)
        if not is_valid:
            err_msg = (
                f"You are not allowed to upload {privacy_type}"
                " layer!"
            )
            if is_update:
                err_msg = (
                    "You are not allowed to update this layer!"
                )
            raise PermissionDenied(err_msg)
        return True

    def save_input_layer(self, upload_param: UploadLayerSerializer, user):
        input_layer: InputLayer = None
        is_new = True
        if upload_param.validated_data.get('uuid', None):
            is_new = False
            input_layer = get_object_or_404(
                InputLayer, uuid=upload_param.validated_data['uuid'])
            self.validate_upload_access(
                upload_param.validated_data['privacy_type'], user,
                True, input_layer)
            input_layer.name = upload_param.validated_data['name']
            input_layer.created_on = timezone.now()
            input_layer.owner = user
            input_layer.layer_type = upload_param.validated_data['layer_type']
            input_layer.size = upload_param.validated_data['size']
            input_layer.component_type = (
                upload_param.validated_data['component_type']
            )
            input_layer.privacy_type = (
                upload_param.validated_data['privacy_type']
            )
            input_layer.client_id = upload_param.validated_data.get(
                'client_id', None)
            input_layer.save(update_fields=[
                'name', 'created_on', 'owner', 'layer_type',
                'size', 'component_type', 'privacy_type',
                'client_id'
            ])
        else:
            input_layer = InputLayer.objects.create(
                name=upload_param.validated_data['name'],
                created_on=timezone.now(),
                owner=user,
                layer_type=upload_param.validated_data['layer_type'],
                size=upload_param.validated_data['size'],
                component_type=upload_param.validated_data['component_type'],
                privacy_type=upload_param.validated_data['privacy_type'],
                client_id=upload_param.validated_data.get('client_id', None)
            )
        return input_layer, is_new


class LayerUpload(BaseLayerUpload):
    """API to upload layer file."""
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
            'Layer UUID for updating existing layer'
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
                    'Success Layer Upload'
                ),
                type=openapi.TYPE_OBJECT,
                properties={
                    'uuid': openapi.Schema(
                        title='Layer UUID',
                        type=openapi.TYPE_STRING
                    ),
                    'size': openapi.Schema(
                        title='Layer size',
                        type=openapi.TYPE_NUMBER
                    ),
                    'name': openapi.Schema(
                        title='Layer name',
                        type=openapi.TYPE_STRING
                    ),
                }
            ),
            400: APIErrorSerializer,
            404: APIErrorSerializer
        }
    )
    def post(self, request, format=None):
        file_obj = request.FILES['file']
        if file_obj is None:
            raise ValidationError('Missing file object!')
        request.data.update({
            'name': file_obj.name,
            'size': file_obj.size
        })
        upload_param = UploadLayerSerializer(data=request.data)
        upload_param.is_valid(raise_exception=True)
        # TODO: validations
        # - layer_type
        # - component_type
        # - upload access
        # - file type, max size (?)
        self.validate_upload_access(
            upload_param.validated_data['privacy_type'], request.user)
        input_layer, _ = self.save_input_layer(upload_param, request.user)
        input_layer.file.save(input_layer.name, file_obj, save=True)
        input_layer.refresh_from_db()
        if input_layer.name != input_layer.file.name:
            input_layer.name = input_layer.file.name
            input_layer.save(update_fields=['name'])
        return Response(status=201, data={
            'uuid': str(input_layer.uuid),
            'name': input_layer.name,
            'size': input_layer.size
        })


class LayerUploadStart(BaseLayerUpload):
    """API to upload layer file direct to Minio."""

    def generate_upload_url(self, input_layer: InputLayer):
        storage_backend = select_input_layer_storage()
        filename = input_layer.name
        file_path = input_layer_dir_path(input_layer, filename)
        available_name = storage_backend.get_available_name(file_path)
        _, final_filename = os.path.split(available_name)
        if input_layer.name != final_filename:
            input_layer.name = final_filename
            input_layer.save(update_fields=['name'])
        return get_presigned_url(available_name)

    @swagger_auto_schema(
        operation_id='layer-upload-start',
        tags=[LAYER_API_TAG],
        manual_parameters=[],
        request_body=UploadLayerSerializer,
        responses={
            200: openapi.Schema(
                description=(
                    'Success Start Layer Upload'
                ),
                type=openapi.TYPE_OBJECT,
                properties={
                    'uuid': openapi.Schema(
                        title='Layer UUID',
                        type=openapi.TYPE_STRING
                    ),
                    'upload_url': openapi.Schema(
                        title='Upload URL',
                        type=openapi.TYPE_STRING
                    ),
                    'name': openapi.Schema(
                        title='Layer name',
                        type=openapi.TYPE_STRING
                    ),
                },
                example={
                    "upload_url": (
                        "https://example.com/cplus/4/ncs_pathway/layer.geojson"
                    )
                }
            ),
            400: APIErrorSerializer,
            404: APIErrorSerializer
        }
    )
    def post(self, request):
        upload_param = UploadLayerSerializer(data=request.data)
        upload_param.is_valid(raise_exception=True)
        self.validate_upload_access(
            upload_param.validated_data['privacy_type'], request.user)
        input_layer, is_new = self.save_input_layer(upload_param, request.user)
        if (
            not is_new and
            input_layer.file.storage.exists(input_layer.file.name)
        ):
            # delete existing file
            input_layer.file = None
            input_layer.save()
        upload_url = self.generate_upload_url(input_layer)
        return Response(status=201, data={
            'uuid': str(input_layer.uuid),
            'upload_url': upload_url,
            'name': input_layer.name
        })


class LayerUploadFinish(APIView):
    """API to upload layer file."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='layer-upload-finish',
        tags=[LAYER_API_TAG],
        responses={
            200: openapi.Schema(
                description=(
                    'Success Upload'
                ),
                type=openapi.TYPE_OBJECT,
                properties={
                    'uuid': openapi.Schema(
                        title='Layer UUID',
                        type=openapi.TYPE_STRING
                    ),
                    'size': openapi.Schema(
                        title='Layer size',
                        type=openapi.TYPE_NUMBER
                    ),
                    'name': openapi.Schema(
                        title='Layer name',
                        type=openapi.TYPE_STRING
                    ),
                }
            ),
            400: APIErrorSerializer,
            404: APIErrorSerializer
        }
    )
    def get(self, request, layer_uuid):
        input_layer = get_object_or_404(InputLayer, uuid=layer_uuid)
        # get filepath
        file_path = input_layer_dir_path(input_layer, input_layer.name)
        storage_backend = select_input_layer_storage()
        # validate filepath exists
        if not storage_backend.exists(file_path):
            raise ValidationError(
                f'Layer file {input_layer.name} does not exist!')
        # validate size match
        storage_file_size = storage_backend.size(file_path)
        if storage_file_size != input_layer.size:
            raise ValidationError(
                'Uploaded layer file size missmatch: '
                f'{convert_size(storage_file_size)} '
                f'should be {convert_size(input_layer.size)}!'
            )
        input_layer.file.name = file_path
        input_layer.save(update_fields=['file'])
        return Response(status=200, data={
            'uuid': str(input_layer.uuid),
            'name': input_layer.name,
            'size': input_layer.size
        })


class LayerDetail(APIView):
    """APIs to fetch and remove layer file."""
    permission_classes = [IsAuthenticated]

    def validate_layer_access(self, input_layer: InputLayer, user):
        if user.is_superuser:
            return True
        if input_layer.privacy_type == InputLayer.PrivacyTypes.COMMON:
            return True
        elif input_layer.privacy_type == InputLayer.PrivacyTypes.INTERNAL:
            return is_internal_user(user)
        return input_layer.owner == user

    @swagger_auto_schema(
        operation_id='layer-detail',
        operation_description='API to fetch layer detail.',
        tags=[LAYER_API_TAG],
        manual_parameters=[PARAM_LAYER_UUID_IN_PATH],
        responses={
            200: InputLayerSerializer,
            400: APIErrorSerializer,
            403: APIErrorSerializer,
            404: APIErrorSerializer
        }
    )
    def get(self, request, *args, **kwargs):
        layer_uuid = kwargs.get('layer_uuid')
        input_layer = get_object_or_404(
            InputLayer, uuid=layer_uuid)
        if not self.validate_layer_access(input_layer, request.user):
            raise PermissionDenied(
                f"You are not allowed to access layer {layer_uuid}!")
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
            403: APIErrorSerializer,
            404: APIErrorSerializer
        }
    )
    def delete(self, request, *args, **kwargs):
        layer_uuid = kwargs.get('layer_uuid')
        input_layer = get_object_or_404(
            InputLayer, uuid=layer_uuid)
        if not self.validate_layer_access(input_layer, request.user):
            raise PermissionDenied(
                f"You are not allowed to delete layer {layer_uuid}!")
        input_layer.delete()
        return Response(status=204)
