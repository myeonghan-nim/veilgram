from uuid import UUID

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Post
from .paginations import PostCursorPagination
from .serializers import PostCreateIn, PostOut, PostDetailOut
from .services import create_post
from polls.models import Vote, Poll


class PostViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Post.objects.all()
    pagination_class = PostCursorPagination

    def _with_related(self, base_qs):
        qs = base_qs.select_related("poll").prefetch_related("assets", "poll__options")
        # 인증 사용자 기준으로 내 표만 붙여서 my_option_id 도출(비인증은 스킵)
        user = self.request.user if self.request and self.request.user.is_authenticated else None
        if user:
            qs = qs.prefetch_related(Prefetch("poll__votes", queryset=Vote.objects.filter(voter=user), to_attr="my_votes"))
        return qs

    def create(self, request):
        """
        POST /api/v1/posts/
        {
            "content": "text ...",
            "asset_ids": ["uuid", ...],                               # optional
            "poll_id": "uuid",                                        # optional
            "poll": {"options": ["A","B"], "allow_multiple": false}   # optional (poll_id와 동시 금지)
        }
        -> { "id": "...", "author": "...", "created_at": "..." }
        """
        ser = PostCreateIn(data=request.data)
        ser.is_valid(raise_exception=True)
        v = ser.validated_data
        try:
            post = create_post(
                author=request.user,
                content=v["content"],
                asset_ids=v.get("asset_ids") or [],
                poll_id=str(v["poll_id"]) if v.get("poll_id") else None,
                poll_options=(v["poll"]["options"] if v.get("poll") else None),
                allow_multiple=(v["poll"].get("allow_multiple", False) if v.get("poll") else False),
            )
        except DjangoValidationError as e:
            detail = getattr(e, "message_dict", None) or getattr(e, "messages", None) or str(e)
            raise DRFValidationError(detail)
        return Response(PostOut(post).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        post = get_object_or_404(self._with_related(self.get_queryset()), pk=pk)
        return Response(PostDetailOut(post).data, status=status.HTTP_200_OK)

    # ----- 타임라인(기본: 내 글, ?author_id=... 지원) -----
    def list(self, request):
        author_id = request.query_params.get("author_id")
        qs = self.get_queryset().order_by("-created_at")
        if author_id:
            try:
                UUID(author_id)
            except Exception:
                raise DRFValidationError({"author_id": "Invalid UUID"})
            qs = qs.filter(author_id=author_id)
        else:
            qs = qs.filter(author_id=request.user.id)

        page = self.paginate_queryset(self._with_related(qs))
        ser = PostDetailOut(page, many=True)
        return self.get_paginated_response(ser.data)
