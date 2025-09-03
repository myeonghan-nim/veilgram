from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .serializers import SearchIn, UserHit, PostHit, HashtagHit
from . import services


def _pack(es_resp):
    hits = [h["_source"] for h in es_resp["hits"]["hits"]]
    total = es_resp["hits"]["total"]["value"] if isinstance(es_resp["hits"]["total"], dict) else es_resp["hits"]["total"]
    return total, hits


class SearchViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

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
