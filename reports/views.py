from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .serializers import UserReportIn, PostReportIn, CommentReportIn, ReportOut
from . import services

UUID_RE = r"(?P<obj_id>[0-9a-fA-F-]{36})"


class ReportsViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["post"], url_path=rf"users/{UUID_RE}")
    def users(self, request, obj_id=None):
        ser = UserReportIn(data=request.data)
        ser.is_valid(raise_exception=True)
        report = services.create_user_report(reporter=request.user, target_user_id=obj_id, reasons=ser.validated_data["reasons"], block=ser.validated_data.get("block", False))
        out = ReportOut.from_instance(report)
        return Response(out.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path=rf"posts/{UUID_RE}")
    def posts(self, request, obj_id=None):
        ser = PostReportIn(data=request.data)
        ser.is_valid(raise_exception=True)
        report = services.create_post_report(reporter=request.user, post_id=obj_id, reasons=ser.validated_data["reasons"], block=ser.validated_data.get("block", False))
        out = ReportOut.from_instance(report)
        return Response(out.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path=rf"comments/{UUID_RE}")
    def comments(self, request, obj_id=None):
        ser = CommentReportIn(data=request.data)
        ser.is_valid(raise_exception=True)
        report = services.create_comment_report(reporter=request.user, comment_id=obj_id, reasons=ser.validated_data["reasons"], block=ser.validated_data.get("block", False))
        out = ReportOut.from_instance(report)
        return Response(out.data, status=status.HTTP_201_CREATED)
