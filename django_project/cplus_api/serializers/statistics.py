from rest_framework import serializers
from django.utils import timezone
from cplus_api.api_views.layer import validate_bbox
from cplus_api.models.statistics import ZonalStatisticsTask

class ZonalStatisticsRequestSerializer(serializers.Serializer):
    """bbox expected to be in 'minx,miny,maxx,maxy' form."""

    bbox = serializers.CharField(required=True)

    def validate_bbox(self, value):
        # normalize list/tuple or string to eventually return a string
        if isinstance(value, (list, tuple)):
            if len(value) == 0:
                raise serializers.ValidationError('Bounding box is required.')
            
            if len(value) == 4:
                value = ','.join(str(v) for v in value)

            else:
                value = value[0] if len(value) == 1 else ','.join(str(v) for v in value)

        if value is None or (isinstance(value, str) and value.strip() == ''):
            raise serializers.ValidationError('Bounding box is required.')
        
        return value

    def validate(self, data):
        try:
            normalized_bbox = self.validate_bbox(data.get('bbox'))
        except serializers.ValidationError:
            raise
        except Exception as exc:
            raise serializers.ValidationError(str(exc))
        
        # Handle using layer validator especially for data type
        try:
            bbox_list = validate_bbox(normalized_bbox)
        except Exception as exc:
            raise serializers.ValidationError(str(exc))

        data['bbox_list'] = bbox_list
        data['bbox'] = normalized_bbox

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
            'started_at',
            'finished_at',
            'last_update',
        ]
        read_only_fields = fields