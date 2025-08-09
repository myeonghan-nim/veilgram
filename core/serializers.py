from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, DeviceCredential


class SignupInputSerializer(serializers.Serializer):
    device_id = serializers.CharField(required=False, allow_blank=True, max_length=128)


class SignupOutputSerializer(serializers.ModelSerializer):
    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)
    device_id = serializers.CharField(read_only=True)
    device_secret = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ("id", "created_at", "access", "refresh", "device_id", "device_secret")
        read_only_fields = fields

    @staticmethod
    def build_response(user: User, device_id: str, device_secret: str):
        refresh = RefreshToken.for_user(user)
        return {
            "id": str(user.id),
            "created_at": user.created_at,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "device_id": device_id,
            "device_secret": device_secret,
        }


class DeviceLoginSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
    device_id = serializers.CharField(max_length=128)
    device_secret = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user_id = attrs["user_id"]
        device_id = attrs["device_id"]
        device_secret = attrs["device_secret"]

        device = DeviceCredential.objects.select_related("user").filter(user_id=user_id, device_id=device_id, is_active=True).first()
        if not device or not device.verify_secret(device_secret):
            raise AuthenticationFailed("Invalid device credential")

        refresh = RefreshToken.for_user(device.user)
        DeviceCredential.objects.filter(pk=device.pk).update()
        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user_id": str(user_id),
        }
