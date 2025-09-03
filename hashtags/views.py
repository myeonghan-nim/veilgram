from datetime import timedelta

from django.utils import timezone
from django.db.models import Count
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Hashtag, PostHashtag
from .serializers import HashtagOut, PopularHashtagOut


class HashtagViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    # GET /api/v1/hashtags?prefix=py
    def list(self, request):
        prefix = (request.query_params.get("prefix") or "").strip().lower()
        qs = Hashtag.objects.all()
        if prefix:
            qs = qs.filter(name__startswith=prefix)
        qs = qs.order_by("name")[:50]
        return Response(HashtagOut(qs.values("name"), many=True).data)

    # GET /api/v1/hashtags/popular?days=7&limit=20
    @action(detail=False, methods=["get"], url_path="popular")
    def popular(self, request):
        days = int(request.query_params.get("days", 7))
        limit = int(request.query_params.get("limit", 20))
        since = timezone.now() - timedelta(days=days)

        qs = PostHashtag.objects.filter(post__created_at__gte=since).values("hashtag__name").annotate(post_count=Count("id")).order_by("-post_count")[:limit]

        data = [{"name": r["hashtag__name"], "post_count": r["post_count"]} for r in qs]
        return Response(PopularHashtagOut(data, many=True).data)
