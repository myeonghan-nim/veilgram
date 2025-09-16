import uuid

from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import F, Q

User = get_user_model()


class Follow(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    follower = models.ForeignKey(User, related_name="following", on_delete=models.CASCADE, db_index=True)
    following = models.ForeignKey(User, related_name="followers", on_delete=models.CASCADE, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "follows"
        constraints = [
            models.UniqueConstraint(fields=["follower", "following"], name="uq_follows_pair"),
            models.CheckConstraint(check=~Q(follower=F("following")), name="ck_follows_not_self"),
        ]
        indexes = [
            models.Index(fields=["follower"], name="idx_follows_follower"),
            models.Index(fields=["following"], name="idx_follows_following"),
        ]


class Block(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, related_name="blocks", on_delete=models.CASCADE, db_index=True)
    blocked_user = models.ForeignKey(User, related_name="blocked_by", on_delete=models.CASCADE, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "blocks"
        constraints = [
            models.UniqueConstraint(fields=["user", "blocked_user"], name="uq_blocks_pair"),
            models.CheckConstraint(check=~Q(user=F("blocked_user")), name="ck_blocks_not_self"),
        ]
        indexes = [
            models.Index(fields=["user"], name="idx_blocks_user"),
            models.Index(fields=["blocked_user"], name="idx_blocks_blocked"),
        ]
