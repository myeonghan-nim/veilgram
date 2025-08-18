import uuid

from django.conf import settings
from django.db import models


class Post(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts", db_index=True)
    content = models.TextField()
    # 1:1 성격이지만 FK로 두고 유니크 제약은 10일차 Poll 구현 시점에 논의
    poll = models.ForeignKey("polls.Poll", on_delete=models.SET_NULL, null=True, blank=True, related_name="posts")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "posts"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["author", "-created_at"], name="idx_post_author_created"),
        ]

    def __str__(self):
        return f"Post<{self.id}> by {self.author_id}"
