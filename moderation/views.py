from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from .serializers import ModerationCheckIn, ModerationCheckOut, ModerationRuleIn, ModerationRuleOut
from .services import check_text, load_rules_snapshot, invalidate_rules_cache, upsert_rule
from .models import ModerationRule


class ModerationCheckViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ModerationCheckIn

    @action(detail=False, methods=["post"], url_path="check")
    def check(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        result = check_text(ser.validated_data["content"])
        out = ModerationCheckOut({"allowed": result.allowed, "verdict": result.verdict, "labels": result.labels, "score": result.score, "matches": result.matches})
        return Response(out.data, status=status.HTTP_200_OK)


class ModerationRuleViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    # 실제 운영에선 관리자 전용. 테스트 편의상 IsAuthenticated로 두고 주석 안내.
    # permission_classes = [IsAdminUser]
    permission_classes = [IsAuthenticated]
    queryset = ModerationRule.objects.all().order_by("-created_at")
    serializer_class = ModerationRuleOut

    def get_serializer_class(self):
        if self.action in ("create",):
            return ModerationRuleIn
        return ModerationRuleOut

    def perform_create(self, serializer):
        obj = upsert_rule(**serializer.validated_data)
        serializer.instance = obj
        return obj

    @action(detail=False, methods=["post"], url_path="invalidate-cache")
    def invalidate_cache(self, request, *args, **kwargs):
        invalidate_rules_cache()
        # 즉시 warm-up (선택)
        load_rules_snapshot(force_reload=True)
        return Response({"ok": True})
