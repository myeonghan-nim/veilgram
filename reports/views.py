from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, OpenApiTypes, extend_schema
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from audits.models import AuditAction
from audits.services import write_audit_log
from common.schema import ErrorOut

from . import services
from .serializers import CommentReportIn, PostReportIn, ReportOut, UserReportIn

UUID_RE = r"(?P<obj_id>[0-9a-fA-F-]{36})"


class ReportsViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = serializers.Serializer

    def _audit_report(self, *, action: str, target_type: str, target_id: str, report, reasons, block: bool):
        """
        신고 생성이 성공한 직후 감사 로그를 남긴다.
        - request에서 IP/UA를 받아 해시 저장(PII 최소화)
        - endpoint는 실제 요청을 자동 기록(예: "POST /api/v1/reports/posts/....")
        """
        write_audit_log(
            action=action,
            user=self.request.user,
            target_type=target_type,
            target_id=target_id,
            request=self.request,
            extra={
                "endpoint": f"{self.request.method} {self.request.path}",
                "reasons": reasons,
                "block": block,
                "report_id": str(report.id),
            },
        )

    @extend_schema(
        tags=["Reports"],
        summary="사용자 신고",
        description="대상 **사용자**에 대해 신고를 생성합니다. 필요 시 동시에 차단(`block=true`)을 수행할 수 있습니다.",
        operation_id="reports_users_create",
        parameters=[OpenApiParameter(name="obj_id", location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="대상 사용자 ID (UUID)")],
        request=UserReportIn,
        responses={
            201: OpenApiResponse(response=ReportOut, description="생성된 신고"),
            400: OpenApiResponse(response=ErrorOut),
            401: OpenApiResponse(response=ErrorOut),
            404: OpenApiResponse(response=ErrorOut),
        },
        examples=[OpenApiExample("요청 예시", value={"reasons": ["spam", "harassment"], "block": True}, request_only=True)],
    )
    @action(detail=False, methods=["post"], url_path=rf"users/{UUID_RE}")
    def users(self, request, obj_id=None):
        ser = UserReportIn(data=request.data)
        ser.is_valid(raise_exception=True)
        report = services.create_user_report(reporter=request.user, target_user_id=obj_id, reasons=ser.validated_data["reasons"], block=ser.validated_data.get("block", False))
        reasons = ser.validated_data["reasons"]
        block = ser.validated_data.get("block", False)
        self._audit_report(action=AuditAction.REPORT_USER, target_type="user", target_id=obj_id, report=report, reasons=reasons, block=block)
        out = ReportOut.from_instance(report)
        return Response(out.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["Reports"],
        summary="포스트 신고",
        description="대상 **포스트**에 대해 신고를 생성합니다. 필요 시 동시에 차단(`block=true`)을 수행할 수 있습니다.",
        operation_id="reports_posts_create",
        parameters=[OpenApiParameter(name="obj_id", location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="대상 포스트 ID (UUID)")],
        request=PostReportIn,
        responses={
            201: OpenApiResponse(response=ReportOut, description="생성된 신고"),
            400: OpenApiResponse(response=ErrorOut),
            401: OpenApiResponse(response=ErrorOut),
            404: OpenApiResponse(response=ErrorOut),
        },
        examples=[OpenApiExample("요청 예시", value={"reasons": ["hate", "nudity"], "block": False}, request_only=True)],
    )
    @action(detail=False, methods=["post"], url_path=rf"posts/{UUID_RE}")
    def posts(self, request, obj_id=None):
        ser = PostReportIn(data=request.data)
        ser.is_valid(raise_exception=True)
        report = services.create_post_report(reporter=request.user, post_id=obj_id, reasons=ser.validated_data["reasons"], block=ser.validated_data.get("block", False))
        reasons = ser.validated_data["reasons"]
        block = ser.validated_data.get("block", False)
        self._audit_report(action=AuditAction.REPORT_POST, target_type="post", target_id=obj_id, report=report, reasons=reasons, block=block)
        out = ReportOut.from_instance(report)
        return Response(out.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["Reports"],
        summary="댓글 신고",
        description="대상 **댓글**에 대해 신고를 생성합니다. 필요 시 동시에 차단(`block=true`)을 수행할 수 있습니다.",
        operation_id="reports_comments_create",
        parameters=[OpenApiParameter(name="obj_id", location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="대상 댓글 ID (UUID)")],
        request=CommentReportIn,
        responses={
            201: OpenApiResponse(response=ReportOut, description="생성된 신고"),
            400: OpenApiResponse(response=ErrorOut),
            401: OpenApiResponse(response=ErrorOut),
            404: OpenApiResponse(response=ErrorOut),
        },
        examples=[OpenApiExample("요청 예시", value={"reasons": ["spam"]}, request_only=True)],
    )
    @action(detail=False, methods=["post"], url_path=rf"comments/{UUID_RE}")
    def comments(self, request, obj_id=None):
        ser = CommentReportIn(data=request.data)
        ser.is_valid(raise_exception=True)
        report = services.create_comment_report(reporter=request.user, comment_id=obj_id, reasons=ser.validated_data["reasons"], block=ser.validated_data.get("block", False))
        reasons = ser.validated_data["reasons"]
        block = ser.validated_data.get("block", False)
        self._audit_report(action=AuditAction.REPORT_COMMENT, target_type="comment", target_id=obj_id, report=report, reasons=reasons, block=block)
        out = ReportOut.from_instance(report)
        return Response(out.data, status=status.HTTP_201_CREATED)
