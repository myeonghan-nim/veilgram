import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Comment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey("posts.Post", on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments")
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies")
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["post", "-created_at"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def clean(self):
        # 대댓글의 post 일치성 보장(다이어그램/도메인 규칙)
        if self.parent_id and self.parent.post_id != self.post_id:
            raise ValidationError({"parent": "Parent comment must belong to the same post."})

    def __str__(self):
        return f"Comment({self.id}) by {self.user_id} on post {self.post_id}"
