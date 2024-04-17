import math
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from core.celery import cancel_task
from core.models.base_task_request import READ_ONLY_STATUS, TaskStatus
from core.models.task_log import TaskLog
from cplus_api.models.scenario import ScenarioTask
from cplus_api.serializers.scenario import (
    ScenarioInputSerializer,
    ScenarioTaskStatusSerializer,
    ScenarioTaskLogListSerializer,
    ScenarioTaskLogSerializer,
    PaginatedScenarioTaskStatusSerializer
)
from cplus_api.serializers.common import (
    APIErrorSerializer
)
from cplus_api.utils.api_helper import (
    SCENARIO_API_TAG,
    PARAM_SCENARIO_UUID_IN_PATH,
    BaseScenarioReadAccess,
    PARAMS_PAGINATION,
    get_page_size
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


class ExecuteScenarioAnalysis(BaseScenarioReadAccess, APIView):
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
        self.validate_user_access(request.user, scenario_task, 'execute')
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


class CancelScenarioAnalysisTask(BaseScenarioReadAccess, APIView):
    """API to cancel ongoing scenario analysis job."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='cancel-scenario-analysis-task',
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
                    )
                },
                example={
                    'uuid': '8c4582ab-15b1-4ed0-b8e4-00640ec10a65'
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
        self.validate_user_access(request.user, scenario_task, 'cancel')
        if scenario_task.status not in READ_ONLY_STATUS:
            raise ValidationError(
                "Unable to cancel job with current status "
                f"{scenario_task.status}. Job is not running!")
        if not scenario_task.task_id:
            raise ValidationError(
                "Unable to cancel job with empty task_id and current status "
                f"{scenario_task.status}. Job is not running!")
        cancel_task(scenario_task.task_id)
        # set status directly as cancelled when task is in the queue
        # because the event handler is not executed by worker
        if scenario_task.status == TaskStatus.QUEUED:
            scenario_task.task_on_cancelled()
        return Response(status=200, data={
            'uuid': str(scenario_task.uuid)
        })


class ScenarioAnalysisTaskStatus(BaseScenarioReadAccess, APIView):
    """API to fetch status from scenario analysis."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='scenario-analysis-task-status',
        tags=[SCENARIO_API_TAG],
        manual_parameters=[PARAM_SCENARIO_UUID_IN_PATH],
        responses={
            200: ScenarioTaskStatusSerializer,
            400: APIErrorSerializer,
            403: APIErrorSerializer,
            404: APIErrorSerializer
        }
    )
    def get(self, request, *args, **kwargs):
        scenario_uuid = kwargs.get('scenario_uuid')
        scenario_task = get_object_or_404(
            ScenarioTask, uuid=scenario_uuid)
        self.validate_user_access(request.user, scenario_task)
        return Response(status=200, data=(
            ScenarioTaskStatusSerializer(scenario_task).data
        ))


class ScenarioAnalysisTaskLogs(BaseScenarioReadAccess, APIView):
    """API to fetch logs from scenario task."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='scenario-analysis-task-logs',
        tags=[SCENARIO_API_TAG],
        manual_parameters=[PARAM_SCENARIO_UUID_IN_PATH],
        responses={
            200: ScenarioTaskLogListSerializer,
            400: APIErrorSerializer,
            403: APIErrorSerializer,
            404: APIErrorSerializer
        }
    )
    def get(self, request, *args, **kwargs):
        scenario_uuid = kwargs.get('scenario_uuid')
        scenario_task = get_object_or_404(
            ScenarioTask, uuid=scenario_uuid)
        self.validate_user_access(request.user, scenario_task)
        scenario_task_ct = ContentType.objects.get(
            app_label="cplus_api", model="scenariotask")
        task_log_qs = TaskLog.objects.filter(
            content_type=scenario_task_ct,
            object_id=scenario_task.pk
        ).order_by('date_time')
        return Response(status=200, data=(
            ScenarioTaskLogSerializer(task_log_qs, many=True).data
        ))


class ScenarioAnalysisHistory(APIView):
    """API to fetch scenario analysis submitted by the user."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='scenario-analysis-history',
        tags=[SCENARIO_API_TAG],
        manual_parameters=PARAMS_PAGINATION,
        responses={
            200: PaginatedScenarioTaskStatusSerializer,
            400: APIErrorSerializer,
            404: APIErrorSerializer
        }
    )
    def get(self, request, *args, **kwargs):
        page = int(request.GET.get('page', '1'))
        page_size = get_page_size(request)
        scenarios = ScenarioTask.objects.filter(
            submitted_by=request.user
        ).order_by('submitted_on')
        # set pagination
        paginator = Paginator(scenarios, page_size)
        total_page = math.ceil(paginator.count / page_size)
        if page > total_page:
            output = []
        else:
            paginated_entities = paginator.get_page(page)
            output = (
                ScenarioTaskStatusSerializer(
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


class ScenarioAnalysisTaskDetail(BaseScenarioReadAccess, APIView):
    """API to fetch scenario detail."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='scenario-analysis-detail',
        tags=[SCENARIO_API_TAG],
        manual_parameters=[PARAM_SCENARIO_UUID_IN_PATH],
        responses={
            200: ScenarioInputSerializer,
            400: APIErrorSerializer,
            403: APIErrorSerializer,
            404: APIErrorSerializer
        }
    )
    def get(self, request, *args, **kwargs):
        scenario_uuid = kwargs.get('scenario_uuid')
        scenario_task = get_object_or_404(
            ScenarioTask, uuid=scenario_uuid)
        self.validate_user_access(request.user, scenario_task)
        return Response(status=200, data=scenario_task.detail)
