import uuid

from django.conf import settings
from django.db import models


class AssetType(models.TextChoices):
    IMAGE = "image", "Image"
    VIDEO = "video", "Video"


class AssetStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    READY = "READY", "Ready"
    FAILED = "FAILED", "Failed"


class Asset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assets", db_index=True)
    # 11일차: Post와 연결(현 시점은 nullable)
    post = models.ForeignKey("posts.Post", on_delete=models.SET_NULL, related_name="assets", null=True, blank=True)
    # 14일차: Comment와 연결(추가) — Post와 동시에 연결 금지
    comment = models.ForeignKey("comments.Comment", on_delete=models.SET_NULL, related_name="assets", null=True, blank=True)

    type = models.CharField(max_length=10, choices=AssetType.choices)
    content_type = models.CharField(max_length=64)
    size_bytes = models.BigIntegerField(null=True, blank=True)
    checksum = models.CharField(max_length=128, null=True, blank=True)

    storage_key = models.CharField(max_length=512, unique=True)
    public_url = models.URLField(max_length=1024)

    status = models.CharField(max_length=16, choices=AssetStatus.choices, default=AssetStatus.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)
    duration = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = "assets"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["owner", "-created_at"], name="idx_asset_owner_created"),
            models.Index(fields=["post"], name="idx_asset_post"),
            models.Index(fields=["comment"], name="idx_asset_comment"),
            models.Index(fields=["status"], name="idx_asset_status"),
        ]
        constraints = [
            # 둘 다 연결 금지(동시에 post, comment 설정 금지) — PENDING 단계(둘 다 None)는 허용
            models.CheckConstraint(
                name="asset_not_both_post_and_comment",
                check=~(models.Q(post__isnull=False) & models.Q(comment__isnull=False)),
            ),
        ]

    def __str__(self):
        return f"Asset<{self.id}> {self.type} {self.status}"
