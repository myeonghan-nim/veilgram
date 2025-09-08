import uuid

from django.conf import settings
from django.db import models

User = settings.AUTH_USER_MODEL


class UserReport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_reports", db_index=True)
    target_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reported_by", db_index=True)
    reasons = models.TextField()  # ERD는 text. 리스트는 직렬화하여 보관(Serializer에서 조인).
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_reports"
        indexes = [
            models.Index(fields=["reporter", "target_user"]),
            models.Index(fields=["created_at"]),
        ]


class PostReport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name="post_reports", db_index=True)
    post = models.ForeignKey("posts.Post", on_delete=models.CASCADE, related_name="reports", db_index=True)
    reasons = models.TextField()
    block = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "post_reports"
        indexes = [
            models.Index(fields=["reporter", "post"]),
            models.Index(fields=["created_at"]),
        ]


class CommentReport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name="comment_reports", db_index=True)
    comment = models.ForeignKey("comments.Comment", on_delete=models.CASCADE, related_name="reports", db_index=True)
    reasons = models.TextField()
    block = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "comment_reports"
        indexes = [
            models.Index(fields=["reporter", "comment"]),
            models.Index(fields=["created_at"]),
        ]
