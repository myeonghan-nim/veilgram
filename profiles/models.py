import uuid

from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class Profile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, related_name="profile", on_delete=models.CASCADE, db_index=True)
    nickname = models.CharField(max_length=20, unique=True, db_index=True)
    status_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "profiles"
        indexes = [
            models.Index(fields=["nickname"], name="idx_profiles_nickname"),
        ]

    def __str__(self):
        return f"{self.nickname} ({self.user_id})"
