import uuid

from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class AuditAction(models.TextChoices):
    LOGIN = "login", "Login"
    LOGOUT = "logout", "Logout"
    CREATE_POST = "create_post", "Create Post"
    UPDATE_POST = "update_post", "Update Post"
    DELETE_POST = "delete_post", "Delete Post"
    CREATE_COMMENT = "create_comment", "Create Comment"
    UPDATE_COMMENT = "update_comment", "Update Comment"
    DELETE_COMMENT = "delete_comment", "Delete Comment"
    FOLLOW = "follow", "Follow"
    UNFOLLOW = "unfollow", "Unfollow"
    VOTE_POLL = "vote_poll", "Vote Poll"
    REPORT_USER = "report_user", "Report User"
    REPORT_POST = "report_post", "Report Post"
    REPORT_COMMENT = "report_comment", "Report Comment"


class AuditLog(models.Model):
    # PII 최소화를 위해 IP/UA는 평문 대신 salted SHA-256 해시만 저장한다.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="audit_logs", db_index=True)
    action = models.CharField(max_length=32, choices=AuditAction.choices, db_index=True)
    target_type = models.CharField(max_length=32, blank=True, default="", db_index=True)  # e.g. "post", "comment", "user"
    target_id = models.UUIDField(null=True, blank=True, db_index=True)
    ip_hash = models.CharField(max_length=64, null=True, blank=True)
    ua_hash = models.CharField(max_length=64, null=True, blank=True)
    extra = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "audit_logs"
        indexes = [
            models.Index(fields=["user", "-created_at"], name="audit_user_created_idx"),
            models.Index(fields=["action", "-created_at"], name="audit_action_created_idx"),
            models.Index(fields=["target_type", "target_id", "-created_at"], name="audit_target_created_idx"),
        ]

    def __str__(self):
        return f"[{self.created_at.isoformat()}] {self.user_id} {self.action} {self.target_type}:{self.target_id}"
