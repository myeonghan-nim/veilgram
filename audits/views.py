from django.db.models import QuerySet
from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiTypes, OpenApiResponse, inline_serializer
from rest_framework import mixins, viewsets, permissions, serializers

from .models import AuditLog, AuditAction
from .serializers import AuditLogOut
from common.schema import ErrorOut

DRFAuditLogOut = inline_serializer(
    name="AuditLogOut",
    fields={
        "id": serializers.UUIDField(),
        "user_id": serializers.UUIDField(help_text="Actor user id"),
        "action": serializers.ChoiceField(choices=[c[0] for c in AuditAction.choices]),
        "target_type": serializers.CharField(required=False, allow_blank=True),
        "target_id": serializers.CharField(required=False, allow_blank=True, help_text="UUID or string"),
        "ip": serializers.CharField(required=False, allow_blank=True),
        "user_agent": serializers.CharField(required=False, allow_blank=True),
        "created_at": serializers.DateTimeField(),
    },
)


class IsAdminOrSelfList(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated


@extend_schema_view(
    list=extend_schema(
        tags=["Audits"],
        summary="감사 로그 조회",
        description=(
            "감사(Audit) 로그를 조회합니다.\n\n"
            "- **Filters**: `action`, `target_type`, `user_id`, `since`, `until`\n"
            "- **user_id 필터**: 관리자만(`is_staff` 또는 `is_superuser`) 적용됩니다. "
            "일반 사용자가 제공하면 **무시**됩니다.\n"
            "- **날짜 형식**: ISO8601(예: `2025-09-15T08:30:00Z`, `2025-09-15T08:30:00+09:00`). "
            "타임존 미지정 시 서버 기본 타임존으로 해석합니다.\n"
            "- 페이지네이션은 DRF 전역 설정을 따릅니다."
        ),
        operation_id="audits_list",
        parameters=[
            OpenApiParameter(
                name="action", location=OpenApiParameter.QUERY, type=OpenApiTypes.STR, required=False, enum=[c[0] for c in AuditAction.choices], description="감사 액션 코드"
            ),
            OpenApiParameter(
                name="target_type", location=OpenApiParameter.QUERY, type=OpenApiTypes.STR, required=False, description='대상 타입(자유 문자열): 예) "post", "comment", "user"'
            ),
            OpenApiParameter(
                name="user_id", location=OpenApiParameter.QUERY, type=OpenApiTypes.UUID, required=False, description="관리자 전용 필터. 일반 사용자는 전달해도 무시됩니다."
            ),
            OpenApiParameter(name="since", location=OpenApiParameter.QUERY, type=OpenApiTypes.DATETIME, required=False, description="이 시각(포함) 이후의 로그"),
            OpenApiParameter(name="until", location=OpenApiParameter.QUERY, type=OpenApiTypes.DATETIME, required=False, description="이 시각(포함) 이전의 로그"),
        ],
        responses={200: OpenApiResponse(response=DRFAuditLogOut), 401: OpenApiResponse(response=ErrorOut), 403: OpenApiResponse(response=ErrorOut)},
    )
)
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
