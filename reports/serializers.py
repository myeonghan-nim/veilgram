from rest_framework import serializers


class _ReasonsListField(serializers.ListField):
    child = serializers.CharField(allow_blank=False, max_length=200)
    allow_empty = False


class UserReportIn(serializers.Serializer):
    reasons = _ReasonsListField()
    block = serializers.BooleanField(required=False, default=False)  # 저장X, 즉시 차단용 플래그


class PostReportIn(serializers.Serializer):
    reasons = _ReasonsListField()
    block = serializers.BooleanField(required=False, default=False)


class CommentReportIn(serializers.Serializer):
    reasons = _ReasonsListField()
    block = serializers.BooleanField(required=False, default=False)


class ReportOut(serializers.Serializer):
    report_id = serializers.UUIDField()
    created_at = serializers.DateTimeField()

    @classmethod
    def from_instance(cls, instance):
        return cls({"report_id": instance.id, "created_at": instance.created_at})
