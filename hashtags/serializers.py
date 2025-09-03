from rest_framework import serializers


class HashtagOut(serializers.Serializer):
    name = serializers.CharField()


class PopularHashtagOut(serializers.Serializer):
    name = serializers.CharField()
    post_count = serializers.IntegerField()
