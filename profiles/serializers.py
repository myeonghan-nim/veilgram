from django.db import IntegrityError, transaction
from rest_framework import serializers

from .models import Profile
from .services.validators import NicknamePolicyValidator, ForbiddenNicknameValidator, normalize_nickname


class ProfileReadSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = Profile
        fields = ("id", "user_id", "nickname", "status_message", "created_at", "updated_at")


class ProfileCreateSerializer(serializers.ModelSerializer):
    nickname = serializers.CharField(
        validators=[NicknamePolicyValidator(), ForbiddenNicknameValidator()],
        max_length=20,
    )
    status_message = serializers.CharField(required=False, allow_blank=True, default="")

    class Meta:
        model = Profile
        fields = ("nickname", "status_message")

    def validate_nickname(self, value: str) -> str:
        return normalize_nickname(value)

    @transaction.atomic
    def create(self, validated_data):
        user = self.context["request"].user
        if Profile.objects.filter(user=user).exists():
            raise serializers.ValidationError({"detail": "Profile already exists for this user."})
        try:
            return Profile.objects.create(user=user, **validated_data)
        except IntegrityError:
            raise serializers.ValidationError({"nickname": "Already taken nickname."})


class ProfileUpdateSerializer(serializers.ModelSerializer):
    nickname = serializers.CharField(required=False, validators=[NicknamePolicyValidator(), ForbiddenNicknameValidator()], max_length=20)

    class Meta:
        model = Profile
        fields = ("nickname", "status_message")

    def validate_nickname(self, value: str) -> str:
        return normalize_nickname(value)

    @transaction.atomic
    def update(self, instance: Profile, validated_data):
        for k, v in validated_data.items():
            setattr(instance, k, v)
        try:
            instance.save()
        except IntegrityError:
            raise serializers.ValidationError({"nickname": "Already taken nickname."})
        return instance
