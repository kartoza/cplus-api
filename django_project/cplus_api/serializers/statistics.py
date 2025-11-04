from rest_framework import serializers
from django.utils import timezone
from cplus_api.api_views.layer import validate_bbox
from cplus_api.models.zonal_statistics import ZonalStatisticsTask

class ZonalStatisticsRequestSerializer(serializers.Serializer):
    """bbox expected to be in 'minx,miny,maxx,maxy' form."""

    bbox = serializers.CharField(required=True)

    def validate_bbox(self, value):
        return validate_bbox(value)

    def validate(self, data):
        data['bbox_list'] = self.validate_bbox(data['bbox'])
        return data


class LayerStatisticsSerializer(serializers.Serializer):
    """Single layer result item returned in task results."""

    uuid = serializers.UUIDField()
    layer_name = serializers.CharField()
    mean_value = serializers.FloatField(allow_null=True)


class ZonalStatisticsTaskSerializer(serializers.ModelSerializer):
    """Serializer for ZonalStatisticsTask model."""

    results = LayerStatisticsSerializer(source='result', many=True, required=False)

    class Meta:
        model = ZonalStatisticsTask
        fields = [
            'uuid',
            'status',
            'progress',
            'results',
            'error_message',
            'submitted_on',
            'submitted_by',
            'started_at',
            'finished_at',
            'last_update',
        ]
        read_only_fields = fields