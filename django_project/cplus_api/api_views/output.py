import math
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.paginator import Paginator
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from django.shortcuts import get_object_or_404
from cplus_api.models.scenario import ScenarioTask
from cplus_api.models.layer import OutputLayer
from cplus_api.serializers.common import (
    APIErrorSerializer
)
from cplus_api.serializers.layer import (
    OutputLayerSerializer,
    PaginatedOutputLayerSerializer,
    OutputLayerListSerializer
)
from cplus_api.utils.api_helper import (
    get_page_size,
    SCENARIO_OUTPUT_API_TAG,
    PARAM_SCENARIO_UUID_IN_PATH,
    BaseScenarioReadAccess,
    PARAMS_PAGINATION
)


class UserScenarioAnalysisOutput(BaseScenarioReadAccess, APIView):
    """API to fetch output list of ScenarioAnalysis"""
    permission_classes = [IsAuthenticated]
    param_all_outputs = openapi.Parameter(
        'fetch_all', openapi.IN_QUERY,
        description='Whether to generate download URL for all outputs',
        type=openapi.TYPE_BOOLEAN,
        default=False,
        required=False
    )

    @swagger_auto_schema(
        operation_id='fetch-scenario-outputs',
        tags=[SCENARIO_OUTPUT_API_TAG],
        manual_parameters=[
            PARAM_SCENARIO_UUID_IN_PATH,
            param_all_outputs
        ] + PARAMS_PAGINATION,
        responses={
            200: PaginatedOutputLayerSerializer,
            400: APIErrorSerializer,
            403: APIErrorSerializer,
            404: APIErrorSerializer
        }
    )
    def get(self, request, *args, **kwargs):
        page = int(request.GET.get('page', '1'))
        page_size = get_page_size(request)
        is_fetch_all = request.GET.get('fetch_all', None)
        if is_fetch_all is not None:
            is_fetch_all = is_fetch_all.lower() == 'true'
        scenario_uuid = kwargs.get('scenario_uuid')
        scenario_task = get_object_or_404(
            ScenarioTask, uuid=scenario_uuid)
        self.validate_user_access(request.user, scenario_task)
        layers = OutputLayer.objects.filter(
            scenario=scenario_task
        ).order_by('id')
        # set pagination
        paginator = Paginator(layers, page_size)
        total_page = math.ceil(paginator.count / page_size)
        if page > total_page:
            output = []
        else:
            paginated_entities = paginator.get_page(page)
            output = (
                OutputLayerSerializer(
                    paginated_entities,
                    many=True,
                    context={
                        'is_fetch_all': is_fetch_all
                    }
                ).data
            )
        return Response(status=200, data={
            'page': page,
            'total_page': total_page,
            'page_size': page_size,
            'results': output
        })


class FetchScenarioAnalysisOutput(BaseScenarioReadAccess, APIView):
    """Generate download URL for scenario outputs by UUIDs."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='fetch-scenario-outputs-by-uuids',
        tags=[SCENARIO_OUTPUT_API_TAG],
        manual_parameters=[
            PARAM_SCENARIO_UUID_IN_PATH
        ],
        request_body=openapi.Schema(
            title='List of scenario output UUID',
            type=openapi.TYPE_ARRAY,
            items=openapi.Items(
                type=openapi.TYPE_STRING
            )
        ),
        responses={
            200: OutputLayerListSerializer,
            400: APIErrorSerializer,
            403: APIErrorSerializer,
            404: APIErrorSerializer
        }
    )
    def post(self, request, *args, **kwargs):
        scenario_uuid = kwargs.get('scenario_uuid')
        scenario_task = get_object_or_404(
            ScenarioTask, uuid=scenario_uuid)
        self.validate_user_access(request.user, scenario_task)
        layers = OutputLayer.objects.filter(
            scenario=scenario_task,
            uuid__in=request.data
        ).order_by('id')
        return Response(status=200, data=(
            OutputLayerSerializer(
                layers, many=True,
                context={
                    'is_fetch_all': True
                }
            ).data
        ))
