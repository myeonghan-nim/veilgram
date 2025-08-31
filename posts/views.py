from uuid import UUID

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import mixins, viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Post, PostLike, Bookmark, Repost
from .paginations import PostCursorPagination
from .serializers import PostCreateIn, PostOut, PostDetailOut, BookmarkOut, RepostOut
from .services import create_post
from polls.models import Vote


class PostViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
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

    # ================= 참여 액션 =================
    @action(detail=True, methods=["post"], url_path="like", permission_classes=[IsAuthenticated])
    def like(self, request, pk=None):
        post = get_object_or_404(Post, pk=pk)
        with transaction.atomic():
            try:
                _, created = PostLike.objects.get_or_create(user=request.user, post=post)
                if not created:
                    return Response({"detail": "Already liked"}, status=status.HTTP_400_BAD_REQUEST)
            except IntegrityError:
                return Response({"detail": "Already liked"}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @like.mapping.delete
    def unlike(self, request, pk=None):
        post = get_object_or_404(Post, pk=pk)
        deleted, _ = PostLike.objects.filter(user=request.user, post=post).delete()
        if deleted == 0:
            return Response({"detail": "Not liked"}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="bookmark", permission_classes=[IsAuthenticated])
    def bookmark(self, request, pk=None):
        post = get_object_or_404(Post, pk=pk)
        with transaction.atomic():
            try:
                _, created = Bookmark.objects.get_or_create(user=request.user, post=post)
                if not created:
                    return Response({"detail": "Already bookmarked"}, status=status.HTTP_400_BAD_REQUEST)
            except IntegrityError:
                return Response({"detail": "Already bookmarked"}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @bookmark.mapping.delete
    def unbookmark(self, request, pk=None):
        post = get_object_or_404(Post, pk=pk)
        deleted, _ = Bookmark.objects.filter(user=request.user, post=post).delete()
        if deleted == 0:
            return Response({"detail": "Not bookmarked"}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)

    # UX는 /share, 모델은 Repost
    @action(detail=True, methods=["post"], url_path="share", permission_classes=[IsAuthenticated])
    def share(self, request, pk=None):
        original = get_object_or_404(Post, pk=pk)
        try:
            with transaction.atomic():
                rp = Repost.objects.create(user=request.user, original_post=original)
        except IntegrityError:
            return Response({"detail": "Already reposted"}, status=status.HTTP_400_BAD_REQUEST)
        return Response(RepostOut(rp).data, status=status.HTTP_201_CREATED)


class BookmarkViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    GET /api/v1/bookmarks/
    """

    serializer_class = BookmarkOut
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Bookmark.objects.filter(user=self.request.user).select_related("post").order_by("-created_at")
