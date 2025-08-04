from rest_framework import serializers

from .models import User


class SignupSerializer(serializers.ModelSerializer):
    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ("id", "created_at", "access", "refresh")
        read_only_fields = ("id", "created_at")
