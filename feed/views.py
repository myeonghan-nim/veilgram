import uuid

from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, OpenApiTypes, extend_schema
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.schema import ErrorOut

from .serializers import FeedPostOut
from .services import fetch_following_feed, fetch_hashtag_feed


class FeedViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = serializers.Serializer

    @extend_schema(
        tags=["Feed"],
        summary="팔로잉 피드 조회",
        description=(
            "로그인 사용자의 팔로잉 사용자들의 최신 게시물 타임라인을 반환합니다.\n"
            "- 페이지네이션: 쿼리 파라미터 `page`(기본=0), `size`(기본=20)\n"
            "- 응답은 게시물 카드의 리스트입니다."
        ),
        operation_id="feed_following",
        parameters=[
            OpenApiParameter(name="page", location=OpenApiParameter.QUERY, type=OpenApiTypes.INT, required=False, description="0부터 시작하는 페이지 인덱스(기본=0)"),
            OpenApiParameter(name="size", location=OpenApiParameter.QUERY, type=OpenApiTypes.INT, required=False, description="페이지 당 개수(기본=20)"),
        ],
        responses={
            200: OpenApiResponse(response=FeedPostOut(many=True), description="팔로잉 피드 항목 리스트"),
            401: OpenApiResponse(response=ErrorOut),
        },
        examples=[OpenApiExample("기본 조회", value=None, request_only=True, description="GET /api/v1/feed/following?page=0&size=20")],
    )
    @action(detail=False, methods=["GET"], url_path="following")
    def following(self, request):
        user_id = uuid.UUID(str(request.user.id))
        page = int(request.query_params.get("page", 0))
        size = int(request.query_params.get("size", 20))
        items = fetch_following_feed(user_id, page, size)
        return Response(FeedPostOut(items, many=True).data)

    @extend_schema(
        tags=["Feed"],
        summary="해시태그 피드 조회",
        description=("지정한 해시태그가 포함된 최신 게시물 타임라인을 반환합니다.\n" "- 경로 파라미터: `tag`\n" "- 페이지네이션: `page`(기본=0), `size`(기본=20)"),
        operation_id="feed_by_hashtag",
        parameters=[
            OpenApiParameter(name="tag", location=OpenApiParameter.PATH, type=OpenApiTypes.STR, required=True, description="해시태그(“#” 제외한 문자열)"),
            OpenApiParameter(name="page", location=OpenApiParameter.QUERY, type=OpenApiTypes.INT, required=False, description="0부터 시작하는 페이지 인덱스(기본=0)"),
            OpenApiParameter(name="size", location=OpenApiParameter.QUERY, type=OpenApiTypes.INT, required=False, description="페이지 당 개수(기본=20)"),
        ],
        responses={
            200: OpenApiResponse(response=FeedPostOut(many=True), description="해시태그 피드 항목 리스트"),
            401: OpenApiResponse(response=ErrorOut),
        },
        examples=[OpenApiExample("기본 조회", value=None, request_only=True, description="GET /api/v1/feed/hashtags/travel?page=0&size=20")],
    )
    @action(detail=False, methods=["GET"], url_path="hashtags/(?P<tag>[^/]+)")
    def hashtag(self, request, tag: str):
        page = int(request.query_params.get("page", 0))
        size = int(request.query_params.get("size", 20))
        items = fetch_hashtag_feed(tag, page, size)
        return Response(FeedPostOut(items, many=True).data)
