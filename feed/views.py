import uuid

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .serializers import FeedPostOut
from .services import fetch_following_feed, fetch_hashtag_feed


class FeedViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["GET"], url_path="following")
    def following(self, request):
        user_id = uuid.UUID(str(request.user.id))
        page = int(request.query_params.get("page", 0))
        size = int(request.query_params.get("size", 20))
        items = fetch_following_feed(user_id, page, size)
        return Response(FeedPostOut(items, many=True).data)

    @action(detail=False, methods=["GET"], url_path="hashtags/(?P<tag>[^/]+)")
    def hashtag(self, request, tag: str):
        page = int(request.query_params.get("page", 0))
        size = int(request.query_params.get("size", 20))
        items = fetch_hashtag_feed(tag, page, size)
        return Response(FeedPostOut(items, many=True).data)
