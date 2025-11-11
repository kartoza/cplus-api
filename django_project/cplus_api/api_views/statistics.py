from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from cplus_api.models.statistics import ZonalStatisticsTask
from cplus_api.serializers.statistics import (
    ZonalStatisticsRequestSerializer,
    ZonalStatisticsTaskSerializer
)
from cplus_api.serializers.common import APIErrorSerializer
from cplus_api.tasks.zonal_statistics import calculate_zonal_statistics
from cplus_api.utils.api_helper import LAYER_API_TAG


class ZonalStatisticsView(APIView):
    """
    GET endpoint to initiate zonal statistics calculation
     for NatureBase layers.
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='zonal-statistics-calculate',
        operation_description=(
            'Initiate the calculation of mean zonal statistics for all '
            'nature base layers within the specified bounding box '
            'in WGS84 coordinates.'
        ),
        tags=[LAYER_API_TAG],
        manual_parameters=[
            openapi.Parameter(
                'bbox',
                openapi.IN_QUERY,
                description='Bounding box in format:'
                ' minx,miny,maxx,maxy (WGS84)',
                type=openapi.TYPE_STRING,
                required=True,
                example='28.0,-26.0,29.0,-25.0'
            )
        ],
        responses={
            202: openapi.Schema(
                description='Task initiated successfully',
                type=openapi.TYPE_OBJECT,
                properties={
                    'task_uuid': openapi.Schema(
                        title='Task UUID',
                        type=openapi.TYPE_STRING,
                        format='uuid'
                    ),
                    'message': openapi.Schema(
                        title='Status message',
                        type=openapi.TYPE_STRING
                    )
                }
            ),
            400: APIErrorSerializer
        }
    )
    def get(self, request, *args, **kwargs):
        serializer = ZonalStatisticsRequestSerializer(data={
            'bbox': request.query_params.get('bbox')
        })
        serializer.is_valid(raise_exception=True)
        bbox_list = serializer.validated_data['bbox_list']
        bbox_str = serializer.validated_data['bbox']
        task = ZonalStatisticsTask.objects.create(
            submitted_on=timezone.now(),
            submitted_by=request.user,
            parameters=bbox_str,
            bbox_minx=bbox_list[0],
            bbox_miny=bbox_list[1],
            bbox_maxx=bbox_list[2],
            bbox_maxy=bbox_list[3]
        )
        # Queue calculation worker
        submit_result = calculate_zonal_statistics.delay(task.id)
        task.task_id = submit_result.id
        task.task_name = calculate_zonal_statistics.name
        task.save(update_fields=['task_id', 'task_name'])

        return Response(
            {
                'task_uuid': str(task.uuid),
                'message': 'Zonal statistics calculation started'
            },
            status=status.HTTP_202_ACCEPTED
        )


class ZonalStatisticsProgressView(APIView):
    """
    GET endpoint to check progress of zonal statistics calculation.
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id='zonal-statistics-progress',
        operation_description='Check the progress and status of a '
        'zonal statistics task.',
        tags=[LAYER_API_TAG],
        manual_parameters=[
            openapi.Parameter(
                'task_uuid',
                openapi.IN_PATH,
                description='Task UUID',
                type=openapi.TYPE_STRING,
                required=True,
                format='uuid'
            )
        ],
        responses={
            200: ZonalStatisticsTaskSerializer,
            404: APIErrorSerializer
        }
    )
    def get(self, request, task_uuid, *args, **kwargs):
        # Super users can view any task.
        if request.user.is_superuser:
            task = get_object_or_404(ZonalStatisticsTask, uuid=task_uuid)
        else:
            task = get_object_or_404(
                ZonalStatisticsTask,
                uuid=task_uuid, submitted_by=request.user
            )

        serializer = ZonalStatisticsTaskSerializer(task)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )
