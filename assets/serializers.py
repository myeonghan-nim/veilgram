from django.conf import settings
from rest_framework import serializers

from .models import Asset, AssetType

IMAGE_WHITELIST = settings.ASSET_LIMITS["IMAGE_MIME_WHITELIST"]
VIDEO_WHITELIST = settings.ASSET_LIMITS["VIDEO_MIME_WHITELIST"]


class PrepareUploadIn(serializers.Serializer):
    type = serializers.ChoiceField(choices=AssetType.choices)
    content_type = serializers.CharField(max_length=64)
    size_bytes = serializers.IntegerField(min_value=1)
    ext = serializers.CharField(max_length=10)

    def validate(self, data):
        mt = data["type"]
        ct = data["content_type"]
        size = data["size_bytes"]
        if mt == AssetType.IMAGE:
            if ct not in IMAGE_WHITELIST:
                raise serializers.ValidationError("Unsupported image content_type")
            if size > settings.ASSET_LIMITS["IMAGE_MAX_BYTES"]:
                raise serializers.ValidationError("Image too large")
        elif mt == AssetType.VIDEO:
            if ct not in VIDEO_WHITELIST:
                raise serializers.ValidationError("Unsupported video content_type")
            if size > settings.ASSET_LIMITS["VIDEO_MAX_BYTES"]:
                raise serializers.ValidationError("Video too large")
        else:
            raise serializers.ValidationError("Unsupported asset type")
        return data


class PrepareUploadOut(serializers.Serializer):
    asset_id = serializers.UUIDField()
    upload_url = serializers.URLField()
    method = serializers.CharField()
    headers = serializers.DictField()
    storage_key = serializers.CharField()
    public_url = serializers.URLField()


class CompleteUploadIn(serializers.Serializer):
    asset_id = serializers.UUIDField()
    etag = serializers.CharField(required=False, allow_blank=True)


class AssetOut(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = ["id", "type", "content_type", "size_bytes", "public_url", "status", "created_at"]
