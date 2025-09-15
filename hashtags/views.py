from datetime import timedelta

from django.utils import timezone
from django.db.models import Count
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, OpenApiTypes, OpenApiExample
from rest_framework import viewsets, serializers
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Hashtag, PostHashtag
from .serializers import HashtagOut, PopularHashtagOut
from common.schema import ErrorOut


class HashtagViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = serializers.Serializer

    # GET /api/v1/hashtags?prefix=py
    @extend_schema(
        tags=["Hashtags"],
        summary="해시태그 자동완성",
        description=("`prefix`로 시작하는 해시태그를 최대 50개까지 사전순으로 반환합니다. " "접두사가 없으면 사전순 상위 50개를 반환합니다."),
        operation_id="hashtags_list",
        parameters=[
            OpenApiParameter(
                name="prefix",
                location=OpenApiParameter.QUERY,
                required=False,
                type=OpenApiTypes.STR,
                description="접두사(대소문자 무시). 예: `py` → `python`, `pytorch` …",
            )
        ],
        responses={
            200: OpenApiResponse(response=HashtagOut(many=True), description="해시태그 이름 목록"),
            401: OpenApiResponse(response=ErrorOut),
        },
        examples=[OpenApiExample("예시", description="자동완성 호출", value=None, request_only=True)],
    )
    def list(self, request):
        prefix = (request.query_params.get("prefix") or "").strip().lower()
        qs = Hashtag.objects.all()
        if prefix:
            qs = qs.filter(name__startswith=prefix)
        qs = qs.order_by("name")[:50]
        return Response(HashtagOut(qs.values("name"), many=True).data)

    # GET /api/v1/hashtags/popular?days=7&limit=20
    @extend_schema(
        tags=["Hashtags"],
        summary="인기 해시태그",
        description=("`days`일 동안 생성된 게시물 중에서 가장 많이 사용된 해시태그를 " "`limit`개 상위 순으로 반환합니다."),
        operation_id="hashtags_popular",
        parameters=[
            OpenApiParameter(name="days", location=OpenApiParameter.QUERY, required=False, type=OpenApiTypes.INT, description="조회 기간(일). 기본=7"),
            OpenApiParameter(name="limit", location=OpenApiParameter.QUERY, required=False, type=OpenApiTypes.INT, description="반환 개수. 기본=20"),
        ],
        responses={
            200: OpenApiResponse(response=PopularHashtagOut(many=True), description="인기 해시태그 목록(이름과 집계 수)"),
            401: OpenApiResponse(response=ErrorOut),
        },
        examples=[OpenApiExample("예시", description="최근 7일 상위 20개", value=None, request_only=True)],
    )
    @action(detail=False, methods=["get"], url_path="popular")
    def popular(self, request):
        days = int(request.query_params.get("days", 7))
        limit = int(request.query_params.get("limit", 20))
        since = timezone.now() - timedelta(days=days)

        qs = PostHashtag.objects.filter(post__created_at__gte=since).values("hashtag__name").annotate(post_count=Count("id")).order_by("-post_count")[:limit]

        data = [{"name": r["hashtag__name"], "post_count": r["post_count"]} for r in qs]
        return Response(PopularHashtagOut(data, many=True).data)
