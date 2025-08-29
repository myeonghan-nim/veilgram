# comments/views.py
from django.shortcuts import get_object_or_404
from rest_framework import mixins, viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Comment
from .permissions import IsAuthorOrReadOnly
from .serializers import CommentSerializer
from posts.models import Post


class PostCommentViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    /api/v1/posts/{post_id}/comments
    - GET: 해당 게시물의 댓글 목록
    - POST: 새 댓글 생성(최상위 또는 parent 지정)
    """

    permission_classes = [IsAuthenticated]
    serializer_class = CommentSerializer

    def get_post(self):
        return get_object_or_404(Post, id=self.kwargs["post_id"])

    def get_queryset(self):
        post = self.get_post()
        # 최신순 기본, 필요 시 created_at asc 정렬 옵션 쿼리파라미터 추가 가능
        return Comment.objects.filter(post=post, parent__isnull=True).select_related("user", "post").prefetch_related("replies")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        if getattr(self, "action", None) in {"update", "partial_update", "destroy", "retrieve"}:
            try:
                obj = self.get_object()
                ctx["post"] = obj.post
            except Exception:
                pass
        return ctx


class CommentViewSet(viewsets.ModelViewSet):
    """
    /api/v1/comments/{id}
    - GET: 단일 댓글 조회
    - PATCH/DELETE: 작성자만
    - /api/v1/comments/{id}/replies: 대댓글 목록/생성
    """

    permission_classes = [IsAuthenticated & IsAuthorOrReadOnly]
    serializer_class = CommentSerializer
    queryset = Comment.objects.select_related("user", "post").all()

    def get_permissions(self):
        # 읽기: 인증만, 수정/삭제: 작성자
        if self.action in ["retrieve", "replies"]:
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsAuthorOrReadOnly()]

    @action(detail=True, methods=["get", "post"], url_path="replies")
    def replies(self, request, pk=None):
        parent = self.get_object()
        if request.method.lower() == "get":
            qs = parent.replies.select_related("user", "post")
            page = self.paginate_queryset(qs)
            ser = self.get_serializer(page or qs, many=True)
            return self.get_paginated_response(ser.data) if page is not None else Response(ser.data)

        # POST (대댓글 생성)
        serializer = self.get_serializer(data={**request.data, "parent": str(parent.id)}, context={"request": request, "post": parent.post})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        out = self.get_serializer(obj).data
        return Response(out, status=status.HTTP_201_CREATED)
