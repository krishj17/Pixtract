from rest_framework import serializers

class ExtractRequestSerializer(serializers.Serializer):
    url = serializers.URLField(required=True)  # URLField validates format for you
    screenshot = serializers.BooleanField(required=False, default=False)
    fields = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=[]
    )