import math
import os
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.contrib.gis.geos import Polygon
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.conf import settings
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from cplus_api.models.layer import (
    BaseLayer, InputLayer, input_layer_dir_path,
    select_input_layer_storage, MultipartUpload,
    TemporaryLayer
)
from cplus_api.models.profile import UserProfile
from cplus_api.serializers.layer import (
    InputLayerSerializer,
    PaginatedInputLayerSerializer,
    UploadLayerSerializer,
    UpdateLayerInputSerializer,
    FinishUploadLayerSerializer,
    LAYER_SCHEMA_FIELDS,
    InputLayerListSerializer
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
    convert_size,
    PARAMS_PAGINATION,
    PARAM_BBOX_IN_QUERY,
    get_multipart_presigned_urls,
    complete_multipart_upload,
    abort_multipart_upload,
    clip_raster
)


def is_internal_user(user):
    """Check if user has internal user role.

    :param user: user object
    :type user: User
    :return: True if user has internal role
    :rtype: bool
    """
    user_profile = UserProfile.objects.filter(
        user=user
    ).first()
    if not user_profile:
        return False
    if not user_profile.role:
        return False
    return user_profile.role.name == 'Internal'


def validate_layer_access(input_layer: InputLayer, user):
    """Validate if user can access input layer.

    :param input_layer: input layer object
    :type input_layer: InputLayer
    :param user: user object
    :type user: User
    :return: True if user has permission to access the layer
    :rtype: bool
    """
    if user.is_superuser:
        return True
    if input_layer.privacy_type == InputLayer.PrivacyTypes.COMMON:
        return True
    elif input_layer.privacy_type == InputLayer.PrivacyTypes.INTERNAL:
        return is_internal_user(user)
    return input_layer.owner == user


def validate_layer_manage(input_layer: InputLayer, user):
    """Validate if user can manage(edit/delete) layer.

    :param input_layer: input layer object
    :type input_layer: InputLayer
    :param user: user object
    :type user: User
    :return: True if user has permission to manage the layer
    :rtype: bool
    """
    # Super user / owner / internal user can manage layer
    return user.is_superuser or input_layer.owner == user \
        or is_internal_user(user)


class LayerList(APIView):
    """API to return available layers."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='layer-list',
        tags=[LAYER_API_TAG],
        manual_parameters=PARAMS_PAGINATION,
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


class DefaultLayerList(APIView):
    """API to return default layers."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='layer-default-list',
        tags=[LAYER_API_TAG],
        responses={
            200: InputLayerListSerializer,
            400: APIErrorSerializer,
            404: APIErrorSerializer
        }
    )
    def get(self, request, *args, **kwargs):
        layers = InputLayer.objects.filter(
            privacy_type=InputLayer.PrivacyTypes.COMMON
        ).order_by('name')
        return Response(status=200, data=(
            InputLayerSerializer(
                layers, many=True
            ).data
        ))


class BaseLayerUpload(APIView):
    """Base class for layer upload."""

    def validate_upload_access(self, privacy_type, user,
                               is_update=False, existing_layer=None):
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
            input_layer.version = upload_param.validated_data.get(
                'version',
                None
            )
            input_layer.license = upload_param.validated_data.get(
                'license',
                None
            )
            input_layer.save(update_fields=[
                'name', 'created_on', 'owner', 'layer_type',
                'size', 'component_type', 'privacy_type',
                'client_id', 'version', 'license'
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
                client_id=upload_param.validated_data.get('client_id', None),
                version=upload_param.validated_data.get('version', None),
                license=upload_param.validated_data.get('license', None)
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

    def generate_upload_url(self, input_layer: InputLayer,
                            number_of_parts=0):
        storage_backend = select_input_layer_storage()
        filename = input_layer.name
        file_path = input_layer_dir_path(input_layer, filename)
        available_name = storage_backend.get_available_name(file_path)
        _, final_filename = os.path.split(available_name)
        if input_layer.name != final_filename:
            input_layer.name = final_filename
            input_layer.save(update_fields=['name'])
        results = []
        upload_id = None
        if number_of_parts <= 1:
            single_url = get_presigned_url(available_name)
            if single_url:
                results.append({
                    'part_number': 1,
                    'url': single_url
                })
        else:
            upload_id, urls = get_multipart_presigned_urls(
                available_name, number_of_parts
            )
            if urls:
                results.extend(urls)
                # create MultipartUpload to store the upload_id
                MultipartUpload.objects.create(
                    upload_id=upload_id,
                    input_layer_uuid=input_layer.uuid,
                    created_on=timezone.now(),
                    uploader=input_layer.owner,
                    parts=number_of_parts
                )
        return results, upload_id

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
                    'upload_urls': openapi.Schema(
                        title='List of Upload Presigned URL',
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Items(
                            type=openapi.TYPE_OBJECT,
                            title='Presigned URL item',
                            properties={
                                'part_number': openapi.Schema(
                                    title='Part number for multipart upload',
                                    type=openapi.TYPE_INTEGER
                                ),
                                'url': openapi.Schema(
                                    title='Presigned URL',
                                    type=openapi.TYPE_STRING
                                )
                            }
                        )
                    ),
                    'name': openapi.Schema(
                        title='Layer name',
                        type=openapi.TYPE_STRING
                    ),
                    'multipart_upload_id': openapi.Schema(
                        title='Multipart Upload Id',
                        type=openapi.TYPE_STRING
                    ),
                },
                example={
                    "upload_url": [
                        {
                            'part_number': 1,
                            'url': (
                                "https://example.com/cplus/4/ncs_pathway"
                                "/layer.geojson"
                            )
                        }
                    ]
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
        if not is_new and input_layer.is_available():
            # delete existing file
            input_layer.file = None
            input_layer.save()
        upload_urls, upload_id = self.generate_upload_url(
            input_layer, upload_param.validated_data['number_of_parts'])
        if len(upload_urls) == 0:
            raise RuntimeError('Cannot generate upload url!')
        return Response(status=201, data={
            'uuid': str(input_layer.uuid),
            'upload_urls': upload_urls,
            'name': input_layer.name,
            'multipart_upload_id': upload_id
        })


class LayerUploadFinish(APIView):
    """API to upload layer file."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='layer-upload-finish',
        tags=[LAYER_API_TAG],
        manual_parameters=[PARAM_LAYER_UUID_IN_PATH],
        request_body=FinishUploadLayerSerializer,
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
    def post(self, request, layer_uuid):
        input_layer = get_object_or_404(InputLayer, uuid=layer_uuid)
        # get filepath
        file_path = input_layer_dir_path(input_layer, input_layer.name)
        upload_param = FinishUploadLayerSerializer(data=request.data)
        upload_param.is_valid(raise_exception=True)
        multipart_upload_id = (
            upload_param.validated_data.get('multipart_upload_id', None)
        )
        if multipart_upload_id:
            # mark multipart as done
            complete_multipart_upload(
                file_path,
                multipart_upload_id,
                upload_param.validated_data['items']
            )
            # remove MultipartUpload when upload is completed
            MultipartUpload.objects.filter(
                upload_id=multipart_upload_id
            ).delete()
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


class LayerUploadAbort(APIView):
    """API to abort multipart upload."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='layer-upload-abort',
        tags=[LAYER_API_TAG],
        manual_parameters=[PARAM_LAYER_UUID_IN_PATH],
        request_body=FinishUploadLayerSerializer,
        responses={
            204: NoContentSerializer,
            400: APIErrorSerializer,
            404: APIErrorSerializer
        }
    )
    def post(self, request, layer_uuid):
        input_layer = get_object_or_404(InputLayer, uuid=layer_uuid)
        # get filepath
        file_path = input_layer_dir_path(input_layer, input_layer.name)
        upload_param = FinishUploadLayerSerializer(data=request.data)
        upload_param.is_valid(raise_exception=True)
        multipart_upload_id = (
            upload_param.validated_data.get('multipart_upload_id', None)
        )
        if not multipart_upload_id:
            raise ValidationError('Missing multipart_upload_id!')
        parts = abort_multipart_upload(file_path, multipart_upload_id)
        if parts == 0:
            # if parts is 0, then can safely remove MultipartUpload
            MultipartUpload.objects.filter(
                upload_id=multipart_upload_id
            ).delete()
            input_layer.delete()
        else:
            # else cron job will check and do abort
            MultipartUpload.objects.filter(
                upload_id=multipart_upload_id
            ).update(
                is_aborted=True,
                aborted_on=timezone.now()
            )
        return Response(status=204)


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
            403: APIErrorSerializer,
            404: APIErrorSerializer
        }
    )
    def get(self, request, *args, **kwargs):
        layer_uuid = kwargs.get('layer_uuid')
        input_layer = get_object_or_404(
            InputLayer, uuid=layer_uuid)
        if not validate_layer_access(input_layer, request.user):
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
        if not validate_layer_manage(input_layer, request.user):
            raise PermissionDenied(
                f"You are not allowed to delete layer {layer_uuid}!"
            )
        input_layer.delete()
        return Response(status=204)

    @swagger_auto_schema(
        operation_id='layer-update-partial',
        operation_description='Partially Update InputLayer.',
        tags=[LAYER_API_TAG],
        manual_parameters=[PARAM_LAYER_UUID_IN_PATH],
        request_body=UpdateLayerInputSerializer,
        responses={
            200: UpdateLayerInputSerializer,
            400: APIErrorSerializer,
            403: APIErrorSerializer,
            404: APIErrorSerializer
        }
    )
    def patch(self, request, *args, **kwargs):
        layer_uuid = kwargs.get('layer_uuid')
        input_layer = get_object_or_404(
            InputLayer, uuid=layer_uuid)
        if not validate_layer_manage(input_layer, request.user):
            raise PermissionDenied(
                f"You are not allowed to update layer {layer_uuid}!"
            )

        layer_param = UpdateLayerInputSerializer(
            data=request.data, partial=True
        )
        layer_param.is_valid(raise_exception=True)
        update_fields = []
        for field, value in layer_param.validated_data.items():
            setattr(input_layer, field, value)
            update_fields.append(field)

        input_layer.save(update_fields=update_fields)
        return Response(
            status=200,
            data=InputLayerSerializer(input_layer).data
        )


class CheckLayer(APIView):
    """API to check whether layer is ready by its identifier."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='check-layer',
        operation_description='API to check whether layer is ready.',
        tags=[LAYER_API_TAG],
        manual_parameters=[
            openapi.Parameter(
                'id_type', openapi.IN_QUERY,
                description='Type of layer id: client_id or layer_uuid',
                type=openapi.TYPE_STRING,
                required=False,
                default='client_id',
                enum=['client_id', 'layer_uuid']
            )
        ],
        request_body=openapi.Schema(
            title='List of layer id',
            type=openapi.TYPE_ARRAY,
            items=openapi.Items(
                type=openapi.TYPE_STRING
            )
        ),
        responses={
            200: openapi.Schema(
                description=(
                    'Check Layer Response'
                ),
                type=openapi.TYPE_OBJECT,
                properties={
                    'available': openapi.Schema(
                        title='List of available layer',
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Items(
                            type=openapi.TYPE_STRING
                        )
                    ),
                    'unavailable': openapi.Schema(
                        title='List of unavailable layer (missing file)',
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Items(
                            type=openapi.TYPE_STRING
                        )
                    ),
                    'Invalid': openapi.Schema(
                        title='List of layer with invalid ID or inaccessible',
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Items(
                            type=openapi.TYPE_STRING
                        )
                    )
                }
            ),
            400: APIErrorSerializer,
            403: APIErrorSerializer,
            404: APIErrorSerializer
        }
    )
    def post(self, request, *args, **kwargs):
        id_type = request.GET.get('id_type', 'client_id')
        filters = {}
        if id_type == 'layer_uuid':
            filters = {
                'uuid__in': request.data
            }
        else:
            filters = {
                'client_id__in': request.data
            }
        layers = InputLayer.objects.filter(
            **filters
        ).order_by('name')
        input_ids = set(request.data)
        ids_found = set()
        ids_available = set()
        ids_not_available = set()
        for layer in layers:
            layer_id = (
                str(layer.uuid) if id_type == 'layer_uuid' else
                layer.client_id
            )
            if not validate_layer_access(layer, request.user):
                continue
            ids_found.add(layer_id)
            if layer.is_available():
                ids_available.add(layer_id)
            else:
                ids_not_available.add(layer_id)
        return Response(status=200, data={
            'available': list(ids_available),
            'unavailable': list(ids_not_available),
            'invalid': list(input_ids - ids_found)
        })


class FetchLayerByClientId(APIView):
    """API to fetch input layer by client id."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='fetch-layer-by-client-id',
        operation_description='API to fetch input layer by client id.',
        tags=[LAYER_API_TAG],
        request_body=openapi.Schema(
            title='List of client id',
            type=openapi.TYPE_ARRAY,
            items=openapi.Items(
                type=openapi.TYPE_STRING
            )
        ),
        responses={
            200: openapi.Schema(
                description=(
                    'Layer List'
                ),
                type=openapi.TYPE_ARRAY,
                items=openapi.Items(**LAYER_SCHEMA_FIELDS),
            ),
            400: APIErrorSerializer,
            403: APIErrorSerializer,
            404: APIErrorSerializer
        }
    )
    def post(self, request, *args, **kwargs):
        layers = InputLayer.objects.filter(
            client_id__in=request.data
        ).order_by('name')
        results = {}
        for layer in layers:
            if not validate_layer_access(layer, request.user):
                continue
            if layer.client_id not in results:
                results[layer.client_id] = layer
            elif not results[layer.client_id].is_available():
                results[layer.client_id] = layer
        return Response(status=200, data=InputLayerSerializer(
            list(results.values()),
            many=True
        ).data)


class ReferenceLayerDownload(APIView):
    """APIs to fetch and remove layer file."""
    permission_classes = [AllowAny]
    authentication_classes = []

    @swagger_auto_schema(
        operation_id='reference-layer-download',
        operation_description='API to download and crop reference layer.',
        tags=[LAYER_API_TAG],
        manual_parameters=[PARAM_BBOX_IN_QUERY],
        responses={
            200: openapi.Response(description='Binary response'),
            404: APIErrorSerializer
        }
    )
    def get(self, request, *args, **kwargs):
        from django.core.exceptions import MultipleObjectsReturned
        try:
            reference_layer = get_object_or_404(
                InputLayer,
                component_type=InputLayer.ComponentTypes.REFERENCE_LAYER
            )
        except MultipleObjectsReturned:
            reference_layer = InputLayer.objects.filter(
                component_type=InputLayer.ComponentTypes.REFERENCE_LAYER
            ).first()
        if reference_layer.is_available():
            basename = os.path.basename(reference_layer.file.name)
            file_path = os.path.join(
                settings.TEMPORARY_LAYER_DIR,
                'reference_layer',
                basename
            )
            if not os.path.exists(file_path):
                file_path = reference_layer.download_to_working_directory(
                    settings.TEMPORARY_LAYER_DIR
                )
            x_accel_redirect = os.path.join('reference_layer', basename)
            file_name = basename

            if 'bbox' in request.query_params:
                bbox = request.query_params.get('bbox')
                bbox = bbox.replace(' ', '').split(',')
                bbox = [float(b) for b in bbox]

                # Calculate the width and height of the bounding box
                width = bbox[2] - bbox[0]
                height = bbox[3] - bbox[1]

                # Calculate 20% expansion
                expand_width = width * 0.2
                expand_height = height * 0.2

                # Create the expanded bounding box
                expanded_bbox = (
                    bbox[0] - expand_width / 2,  # min_x
                    bbox[1] - expand_height / 2,  # min_y
                    bbox[2] + expand_width / 2,  # max_x
                    bbox[3] + expand_height / 2  # max_y
                )

                # Convert the expanded bounding box to a Polygon
                expanded_polygon = Polygon.from_bbox(expanded_bbox)

                # Clip the raster
                file_path = clip_raster(
                    file_path,
                    expanded_polygon.extent,
                    settings.TEMPORARY_LAYER_DIR
                )

                # Create temporary layer object
                TemporaryLayer.objects.create(
                    file_name=os.path.basename(file_path),
                    size=os.path.getsize(file_path)
                )
                file_name = os.path.basename(file_path)
                x_accel_redirect = file_name

            # fix issue nginx unable to read file
            os.chmod(file_path, 0o644)
            response = Response(status=200)
            response['Content-type'] = "application/octet-stream"
            response['X-Accel-Redirect'] = (
                f'/userfiles/{x_accel_redirect}'
            )
            response['Content-Disposition'] = (
                f'attachment; filename="{file_name}"'
            )

            return response

        return Response(
            data={'detail': 'Reference layer is not available.'},
            status=404
        )


class DefaultLayerDownload(APIView):
    """API to crop and download priority layer."""
    permission_classes = [AllowAny]
    authentication_classes = []

    @swagger_auto_schema(
        operation_id='default-priority-layer-download',
        operation_description='API to crop and download priority layer.',
        tags=[LAYER_API_TAG],
        manual_parameters=[PARAM_LAYER_UUID_IN_PATH, PARAM_BBOX_IN_QUERY],
        responses={
            200: openapi.Response(description='Binary response'),
            404: APIErrorSerializer
        }
    )
    def get(self, request, *args, **kwargs):
        layer_uuid = kwargs.get('layer_uuid')
        default_layer = get_object_or_404(
            InputLayer,
            uuid=layer_uuid,
            component_type=InputLayer.ComponentTypes.PRIORITY_LAYER
        )
        if default_layer.is_available():
            basename = os.path.basename(default_layer.file.name)
            file_path = os.path.join(
                settings.TEMPORARY_LAYER_DIR,
                'default_layer',
                basename
            )
            if not os.path.exists(file_path):
                file_path = default_layer.download_to_working_directory(
                    settings.TEMPORARY_LAYER_DIR
                )
            x_accel_redirect = os.path.join('default_layer', basename)
            file_name = basename

            if 'bbox' in request.query_params:
                bbox = request.query_params.get('bbox')
                bbox = bbox.replace(' ', '').split(',')
                bbox = [float(b) for b in bbox]

                # Convert the bounding box to a Polygon
                polygon = Polygon.from_bbox(bbox)

                # Clip the raster
                file_path = clip_raster(
                    file_path,
                    polygon.extent,
                    settings.TEMPORARY_LAYER_DIR
                )

                # Create temporary layer object
                TemporaryLayer.objects.create(
                    file_name=os.path.basename(file_path),
                    size=os.path.getsize(file_path)
                )
                file_name = os.path.basename(file_path)
                x_accel_redirect = file_name

            # fix issue nginx unable to read file
            os.chmod(file_path, 0o644)
            response = Response(status=200)
            response['Content-type'] = "application/octet-stream"
            response['X-Accel-Redirect'] = (
                f'/userfiles/{x_accel_redirect}'
            )
            response['Content-Disposition'] = (
                f'attachment; filename="{file_name}"'
            )

            return response

        return Response(
            data={'detail': 'Default layer is not available.'},
            status=404
        )
