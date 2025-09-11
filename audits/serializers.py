from rest_framework import serializers

from .models import AuditLog


class AuditLogOut(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = ["id", "user", "action", "target_type", "target_id", "extra", "created_at"]
        read_only_fields = fields
