from rest_framework import serializers

from .models import Device, NotificationSetting, Notification


class DeviceIn(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = ("platform", "device_token")


class DeviceOut(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = ("id", "platform", "device_token", "is_active", "created_at")


class NotificationSettingOut(serializers.ModelSerializer):
    class Meta:
        model = NotificationSetting
        fields = ("follow", "post", "comment", "like", "updated_at")


class NotificationSettingIn(serializers.Serializer):
    follow = serializers.BooleanField(required=False)
    post = serializers.BooleanField(required=False)
    comment = serializers.BooleanField(required=False)
    like = serializers.BooleanField(required=False)


class NotificationOut(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ("id", "type", "payload", "is_read", "created_at")


class MarkReadIn(serializers.Serializer):
    ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
