from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, OpenApiTypes, extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.schema import ErrorOut, SearchOut

from . import services
from .serializers import HashtagHit, PostHit, SearchIn, UserHit


def _pack(es_resp):
    hits = [h["_source"] for h in es_resp["hits"]["hits"]]
    total = es_resp["hits"]["total"]["value"] if isinstance(es_resp["hits"]["total"], dict) else es_resp["hits"]["total"]
    return total, hits


@extend_schema_view(
    list=extend_schema(
        tags=["Search"],
        summary="통합 검색",
        description=(
            "텍스트 질의로 통합 검색을 수행합니다.\n\n"
            "- `q`(필수): 검색어, 최대 200자\n"
            "- `page`(기본=1, 최소=1)\n"
            "- `size`(기본=10, 1~100)\n"
            "- 응답은 `{ total, results[] }` 형식이며, `results[]`의 항목 구조는 대상 리소스에 따라 달라질 수 있습니다."
        ),
        operation_id="search_list",
        parameters=[
            OpenApiParameter(name="q", location=OpenApiParameter.QUERY, required=True, type=OpenApiTypes.STR, description="검색어(최대 200자)"),
            OpenApiParameter(name="page", location=OpenApiParameter.QUERY, required=False, type=OpenApiTypes.INT, description="페이지 번호(기본=1, 최소=1)"),
            OpenApiParameter(name="size", location=OpenApiParameter.QUERY, required=False, type=OpenApiTypes.INT, description="페이지 크기(기본=10, 1~100)"),
        ],
        responses={
            200: OpenApiResponse(response=SearchOut, description="검색 결과"),
            400: OpenApiResponse(response=ErrorOut),
            401: OpenApiResponse(response=ErrorOut),
        },
        examples=[
            OpenApiExample("사용자 검색 예시", value=None, request_only=True, description="GET /api/v1/search?q=alice&page=1&size=10"),
            OpenApiExample("포스트 검색 예시", value=None, request_only=True, description="GET /api/v1/search?q=%23travel&page=2&size=20"),
            OpenApiExample("해시태그 검색 예시", value=None, request_only=True, description="GET /api/v1/search?q=python&page=1&size=10"),
        ],
    )
)
class SearchViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = SearchIn

    @action(detail=False, methods=["get"], url_path="users")
    def users(self, request):
        params = SearchIn(data=request.query_params)
        params.is_valid(raise_exception=True)
        es = services.search_users(**params.validated_data)
        total, hits = _pack(es)
        return Response({"total": total, "results": UserHit(hits, many=True).data})

    @action(detail=False, methods=["get"], url_path="posts")
    def posts(self, request):
        params = SearchIn(data=request.query_params)
        params.is_valid(raise_exception=True)
        es = services.search_posts(**params.validated_data)
        total, hits = _pack(es)
        return Response({"total": total, "results": PostHit(hits, many=True).data})

    @action(detail=False, methods=["get"], url_path="hashtags")
    def hashtags(self, request):
        params = SearchIn(data=request.query_params)
        params.is_valid(raise_exception=True)
        es = services.search_hashtags(**params.validated_data)
        total, hits = _pack(es)
        return Response({"total": total, "results": HashtagHit(hits, many=True).data})
