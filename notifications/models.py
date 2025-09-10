import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Device(models.Model):
    class Platform(models.TextChoices):
        ANDROID = "android", "Android"
        IOS = "ios", "iOS"
        WEB = "web", "Web"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_index=True)
    platform = models.CharField(max_length=16, choices=Platform.choices)
    device_token = models.CharField(max_length=256, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "devices"
        indexes = [models.Index(fields=["user", "platform"])]


class NotificationSetting(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, unique=True)
    follow = models.BooleanField(default=True)
    post = models.BooleanField(default=True)
    comment = models.BooleanField(default=True)
    like = models.BooleanField(default=True)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "notification_settings"


class Notification(models.Model):
    class Type(models.TextChoices):
        FOLLOW = "follow", "Follow"
        POST = "post", "Post"
        COMMENT = "comment", "Comment"
        LIKE = "like", "Like"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_index=True)
    type = models.CharField(max_length=16, choices=Type.choices)
    payload = models.JSONField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "notifications"
        indexes = [models.Index(fields=["user", "is_read", "-created_at"])]
