from rest_framework import serializers


class SearchIn(serializers.Serializer):
    q = serializers.CharField(max_length=200)
    page = serializers.IntegerField(min_value=1, required=False, default=1)
    size = serializers.IntegerField(min_value=1, max_value=100, required=False, default=10)


class UserHit(serializers.Serializer):
    id = serializers.UUIDField()
    nickname = serializers.CharField()
    status_message = serializers.CharField(allow_blank=True)
    created_at = serializers.DateTimeField()


class PostHit(serializers.Serializer):
    id = serializers.UUIDField()
    author_id = serializers.UUIDField()
    author_nickname = serializers.CharField(allow_blank=True)
    content = serializers.CharField(allow_blank=True)
    hashtags = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    created_at = serializers.DateTimeField()
    like_count = serializers.IntegerField()


class HashtagHit(serializers.Serializer):
    name = serializers.CharField()
    post_count = serializers.IntegerField()
