from rest_framework import serializers


class FeedPostOut(serializers.Serializer):
    post_id = serializers.UUIDField()
    author_id = serializers.UUIDField()
    created_at = serializers.CharField()
