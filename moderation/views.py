from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, OpenApiTypes, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.schema import ErrorOut, OkOut

from .models import ModerationRule
from .serializers import ModerationCheckIn, ModerationCheckOut, ModerationRuleIn, ModerationRuleOut
from .services import check_text, invalidate_rules_cache, load_rules_snapshot, upsert_rule


class ModerationCheckViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ModerationCheckIn

    @extend_schema(
        tags=["Moderation"],
        summary="텍스트 모더레이션 검사",
        description=(
            "입력된 텍스트에 대해 금칙어/정책 위반 여부를 검사합니다.\n"
            "- `allowed`: 허용 여부\n"
            "- `verdict`: 판정 사유(간단 메시지)\n"
            "- `labels`: 매칭된 라벨 목록(예: spam, abuse)\n"
            "- `score`: 위험도/신뢰도 점수\n"
            "- `matches`: 매칭된 패턴/키워드 정보"
        ),
        operation_id="moderation_check",
        request=ModerationCheckIn,
        responses={
            200: OpenApiResponse(response=ModerationCheckOut, description="검사 결과"),
            400: OpenApiResponse(response=ErrorOut),
            401: OpenApiResponse(response=ErrorOut),
        },
        examples=[
            OpenApiExample("요청 예시", value={"content": "buy cheap followers now!"}, request_only=True),
            OpenApiExample(
                "응답 예시",
                value={"allowed": False, "verdict": "blocked_by_keyword", "labels": ["spam"], "score": 0.97, "matches": [{"type": "deny_keyword", "pattern": "followers"}]},
                response_only=True,
            ),
        ],
    )
    @action(detail=False, methods=["post"], url_path="check")
    def check(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        result = check_text(ser.validated_data["content"])
        out = ModerationCheckOut({"allowed": result.allowed, "verdict": result.verdict, "labels": result.labels, "score": result.score, "matches": result.matches})
        return Response(out.data, status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(
        tags=["Moderation"],
        summary="모더레이션 규칙 목록",
        description="등록된 모더레이션 규칙을 최신순으로 반환합니다. 페이지네이션은 전역 DRF 설정을 따릅니다.",
        operation_id="moderation_rules_list",
        responses={
            200: OpenApiResponse(response=ModerationRuleOut(many=True), description="규칙 목록"),
            401: OpenApiResponse(response=ErrorOut),
            403: OpenApiResponse(response=ErrorOut),
        },
    ),
    create=extend_schema(
        tags=["Moderation"],
        summary="모더레이션 규칙 생성/업서트",
        description="`rule_type`과 `pattern`으로 규칙을 생성합니다(동일 패턴은 업서트 처리).",
        operation_id="moderation_rules_create",
        request=ModerationRuleIn,
        responses={
            201: OpenApiResponse(response=ModerationRuleOut, description="생성(또는 갱신)된 규칙"),
            400: OpenApiResponse(response=ErrorOut),
            401: OpenApiResponse(response=ErrorOut),
            403: OpenApiResponse(response=ErrorOut),
        },
        examples=[OpenApiExample("예시", value={"rule_type": "deny_keyword", "pattern": "spam"}, request_only=True)],
    ),
    destroy=extend_schema(
        tags=["Moderation"],
        summary="모더레이션 규칙 삭제",
        operation_id="moderation_rules_destroy",
        parameters=[OpenApiParameter(name="pk", location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="삭제할 규칙 ID (UUID)")],
        responses={
            204: OpenApiResponse(description="삭제 성공"),
            401: OpenApiResponse(response=ErrorOut),
            403: OpenApiResponse(response=ErrorOut),
            404: OpenApiResponse(response=ErrorOut),
        },
    ),
)
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

    @extend_schema(
        tags=["Moderation"],
        summary="규칙 캐시 무효화(옵션: 즉시 워밍업)",
        description="서버의 규칙 캐시를 무효화하고 스냅샷을 즉시 재적재합니다.",
        operation_id="moderation_rules_invalidate_cache",
        responses={200: OpenApiResponse(response=OkOut, description="ok 플래그 반환"), 401: OpenApiResponse(response=ErrorOut), 403: OpenApiResponse(response=ErrorOut)},
        examples=[OpenApiExample("응답 예시", value={"ok": True}, response_only=True)],
    )
    @action(detail=False, methods=["post"], url_path="invalidate-cache")
    def invalidate_cache(self, request, *args, **kwargs):
        invalidate_rules_cache()
        # 즉시 warm-up (선택)
        load_rules_snapshot(force_reload=True)
        return Response({"ok": True})
