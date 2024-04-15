from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from core.models.base_task_request import READ_ONLY_STATUS
from cplus_api.models.scenario import ScenarioTask
from cplus_api.serializers.scenario import (
    ScenarioInputSerializer
)
from cplus_api.serializers.common import (
    APIErrorSerializer
)
from cplus_api.utils.api_helper import (
    SCENARIO_API_TAG,
    PARAM_SCENARIO_UUID_IN_PATH
)
from cplus_api.tasks.runner import run_scenario_analysis_task


class ScenarioAnalysisSubmit(APIView):
    """API to submit scenario detail."""
    permission_classes = [IsAuthenticated]

    def fetch_api_version(self, request):
        version = 'v1'
        resolver_match = getattr(request, 'resolver_match', None)
        possible_versions = []
        if resolver_match and resolver_match.namespace:
            possible_versions = resolver_match.namespace.split(':')
        if possible_versions:
            version = possible_versions[0]
        return version

    @swagger_auto_schema(
        operation_id='submit-scenario-detail',
        tags=[SCENARIO_API_TAG],
        manual_parameters=[
            openapi.Parameter(
                'plugin_version', openapi.IN_QUERY,
                description=(
                    'Version of the plugin'
                ),
                type=openapi.TYPE_STRING,
                required=False
            )
        ],
        request_body=ScenarioInputSerializer,
        responses={
            201: openapi.Schema(
                description=(
                    'Success'
                ),
                type=openapi.TYPE_OBJECT,
                properties={
                    'uuid': openapi.Schema(
                        title='Scenario UUID',
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
        plugin_version = request.GET.get('plugin_version', '0.0.1')
        api_version = self.fetch_api_version(request)
        serializer = ScenarioInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # TODO: validate scenario detail
        scenario_task = ScenarioTask.objects.create(
            submitted_on=timezone.now(),
            submitted_by=request.user,
            api_version=api_version,
            plugin_version=plugin_version,
            detail=request.data
        )
        return Response(status=201, data={
            'uuid': str(scenario_task.uuid)
        })


class ExecuteScenarioAnalysis(APIView):
    """API to execute scenario analysis."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='execute-scenario-analysis',
        tags=[SCENARIO_API_TAG],
        manual_parameters=[PARAM_SCENARIO_UUID_IN_PATH],
        responses={
            200: openapi.Schema(
                description=(
                    'Execution Detail'
                ),
                type=openapi.TYPE_OBJECT,
                properties={
                    'uuid': openapi.Schema(
                        title='Scenario UUID',
                        type=openapi.TYPE_STRING
                    ),
                    'task_id': openapi.Schema(
                        title='Task ID',
                        type=openapi.TYPE_STRING
                    )
                },
                example={
                    'uuid': '8c4582ab-15b1-4ed0-b8e4-00640ec10a65',
                    'task_id': '8f27c431-d416-492f-98ba-6a52cc20fa2e'
                }
            ),
            400: APIErrorSerializer,
            403: APIErrorSerializer,
            404: APIErrorSerializer
        }
    )
    def get(self, request, *args, **kwargs):
        scenario_uuid = kwargs.get('scenario_uuid')
        scenario_task = get_object_or_404(
            ScenarioTask, uuid=scenario_uuid)
        if scenario_task.submitted_by != request.user:
            raise PermissionDenied(
                f"You are not allowed to execute scenario {scenario_uuid}!")
        if scenario_task.status in READ_ONLY_STATUS:
            raise ValidationError(
                "Unable to start job with current status "
                f"{scenario_task.status}. "
                "Please cancel the current task first!")
        task = run_scenario_analysis_task.apply_async(
            (scenario_task.id,), queue='cplus')
        return Response(status=201, data={
            'uuid': str(scenario_task.uuid),
            'task_id': str(task.id)
        })
