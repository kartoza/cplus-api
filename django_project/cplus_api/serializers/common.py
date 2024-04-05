from rest_framework import serializers


class APIErrorSerializer(serializers.Serializer):
    detail = serializers.CharField()


class NoContentSerializer(serializers.Serializer):
    pass
