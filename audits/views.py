from django.db.models import QuerySet
from django.utils.dateparse import parse_datetime
from rest_framework import mixins, viewsets, permissions

from .models import AuditLog
from .serializers import AuditLogOut


class IsAdminOrSelfList(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated


class AuditLogViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    - 일반 사용자: 자신의 로그만 조회
    - 스태프: user_id 필터로 임의 사용자 로그 조회 가능
    - 필터: action, target_type, since(ISO8601), until(ISO8601)
    """

    permission_classes = [IsAdminOrSelfList]
    serializer_class = AuditLogOut

    def get_queryset(self) -> QuerySet:
        qs = AuditLog.objects.all().order_by("-created_at")
        u = self.request.user

        is_admin = bool(getattr(u, "is_superuser", False) or getattr(u, "is_staff", False))
        if not is_admin:
            qs = qs.filter(user=u)

        # filters
        action = self.request.query_params.get("action")
        target_type = self.request.query_params.get("target_type")
        since = self.request.query_params.get("since")
        until = self.request.query_params.get("until")
        user_id = self.request.query_params.get("user_id")  # staff only

        if action:
            qs = qs.filter(action=action)
        if target_type:
            qs = qs.filter(target_type=target_type)
        if since:
            dt = parse_datetime(since)
            if dt:
                qs = qs.filter(created_at__gte=dt)
        if until:
            dt = parse_datetime(until)
            if dt:
                qs = qs.filter(created_at__lte=dt)
        if user_id and is_admin:
            qs = qs.filter(user_id=user_id)

        return qs
