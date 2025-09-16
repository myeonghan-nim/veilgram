from uuid import UUID

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, OpenApiTypes, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from audits.models import AuditAction
from audits.services import write_audit_log
from common.schema import ErrorOut
from polls.models import Vote

from .models import Bookmark, Post, PostLike, Repost
from .paginations import PostCursorPagination
from .serializers import BookmarkOut, PostCreateIn, PostDetailOut, PostOut, RepostOut
from .services import create_post


@extend_schema_view(
    create=extend_schema(
        tags=["Posts"],
        summary="새 포스트 작성",
        description=(
            "텍스트 기반 포스트를 생성하며, 사전 업로드한 자산(이미지/동영상)과 투표를 함께 첨부할 수 있습니다.\n"
            "- `asset_ids`: Assets 서비스에서 준비/완료된 자산의 ID 목록\n"
            "- `poll_id` 또는 `poll`(동시 지정 금지): 기존 투표 연결 또는 새 투표 생성\n"
        ),
        operation_id="posts_create",
        request=PostCreateIn,
        responses={201: OpenApiResponse(response=PostOut, description="생성된 포스트 요약"), 400: OpenApiResponse(response=ErrorOut), 401: OpenApiResponse(response=ErrorOut)},
        examples=[
            OpenApiExample("텍스트+이미지", value={"content": "주말 사진 공유합니다!", "asset_ids": ["11111111-1111-1111-1111-111111111111"]}, request_only=True),
            OpenApiExample(
                "텍스트+투표(신규 생성)", value={"content": "점심 뭐먹지?", "poll": {"options": ["국밥", "비빔밥", "김치찌개"], "allow_multiple": False}}, request_only=True
            ),
        ],
    ),
    retrieve=extend_schema(
        tags=["Posts"],
        summary="포스트 단건 조회",
        operation_id="posts_retrieve",
        parameters=[OpenApiParameter(name="pk", location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="포스트 ID (UUID)")],
        responses={200: OpenApiResponse(response=PostDetailOut), 401: OpenApiResponse(response=ErrorOut), 404: OpenApiResponse(response=ErrorOut)},
    ),
    list=extend_schema(
        tags=["Posts"],
        summary="포스트 목록(기본: 내 글, author 필터 가능)",
        description=("기본적으로 **내가 작성한 글**을 최신순으로 페이지네이션해 반환합니다.\n" "`author_id`를 주면 해당 사용자의 글로 필터합니다."),
        operation_id="posts_list",
        parameters=[OpenApiParameter(name="author_id", location=OpenApiParameter.QUERY, type=OpenApiTypes.UUID, required=False, description="작성자 ID(미지정 시 현재 사용자)")],
        responses={200: OpenApiResponse(response=PostDetailOut, description="커서 페이지네이션 적용 목록"), 401: OpenApiResponse(response=ErrorOut)},
    ),
)
class PostViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Post.objects.all()
    pagination_class = PostCursorPagination

    def _audit_post(self, action, post, extra=None):
        """
        posts의 주요 상태 변경 직후 한 줄로 감사 로그를 남기기 위한 헬퍼.
        - target_type: 'post'
        - target_id: 해당 post.id
        - request를 넘겨 IP/UA 해시 자동 저장
        """
        write_audit_log(action=action, user=self.request.user, target_type="post", target_id=str(post.id), request=self.request, extra=extra or {})

    def _with_related(self, base_qs):
        qs = base_qs.select_related("poll").prefetch_related("assets", "poll__options")
        # 인증 사용자 기준으로 내 표만 붙여서 my_option_id 도출(비인증은 스킵)
        user = self.request.user if self.request and self.request.user.is_authenticated else None
        if user:
            qs = qs.prefetch_related(Prefetch("poll__votes", queryset=Vote.objects.filter(voter=user), to_attr="my_votes"))
        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return PostCreateIn
        if self.action in ("retrieve", "list"):
            return PostDetailOut
        if self.action == "share":
            return RepostOut
        return PostDetailOut

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

        self._audit_post(AuditAction.CREATE_POST, post, {"endpoint": "POST /api/v1/posts"})
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
    @extend_schema(
        tags=["Posts/Engagements"],
        summary="좋아요",
        operation_id="posts_like",
        parameters=[OpenApiParameter(name="pk", location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="포스트 ID")],
        responses={
            204: OpenApiResponse(description="좋아요 성공"),
            400: OpenApiResponse(response=ErrorOut, description="이미 좋아요한 경우"),
            401: OpenApiResponse(response=ErrorOut),
            404: OpenApiResponse(response=ErrorOut),
        },
    )
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

        self._audit_post(AuditAction.CREATE_POST, post, {"endpoint": "POST /api/v1/posts"})
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        tags=["Posts/Engagements"],
        summary="좋아요 취소",
        operation_id="posts_unlike",
        parameters=[OpenApiParameter(name="pk", location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="포스트 ID")],
        responses={
            204: OpenApiResponse(description="좋아요 취소 성공"),
            401: OpenApiResponse(response=ErrorOut),
            404: OpenApiResponse(response=ErrorOut, description="좋아요하지 않은 경우"),
        },
    )
    @like.mapping.delete
    def unlike(self, request, pk=None):
        post = get_object_or_404(Post, pk=pk)
        deleted, _ = PostLike.objects.filter(user=request.user, post=post).delete()
        if deleted == 0:
            return Response({"detail": "Not liked"}, status=status.HTTP_404_NOT_FOUND)

        self._audit_post(AuditAction.CREATE_POST, post, {"endpoint": "POST /api/v1/posts"})
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        tags=["Posts/Engagements"],
        summary="북마크",
        operation_id="posts_bookmark",
        parameters=[OpenApiParameter(name="pk", location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="포스트 ID")],
        responses={
            204: OpenApiResponse(description="북마크 성공"),
            400: OpenApiResponse(response=ErrorOut, description="이미 북마크한 경우"),
            401: OpenApiResponse(response=ErrorOut),
            404: OpenApiResponse(response=ErrorOut),
        },
    )
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

        self._audit_post(AuditAction.CREATE_POST, post, {"endpoint": "POST /api/v1/posts"})
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        tags=["Posts/Engagements"],
        summary="북마크 취소",
        operation_id="posts_unbookmark",
        parameters=[OpenApiParameter(name="pk", location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="포스트 ID")],
        responses={
            204: OpenApiResponse(description="북마크 취소 성공"),
            401: OpenApiResponse(response=ErrorOut),
            404: OpenApiResponse(response=ErrorOut, description="북마크하지 않은 경우"),
        },
    )
    @bookmark.mapping.delete
    def unbookmark(self, request, pk=None):
        post = get_object_or_404(Post, pk=pk)
        deleted, _ = Bookmark.objects.filter(user=request.user, post=post).delete()
        if deleted == 0:
            return Response({"detail": "Not bookmarked"}, status=status.HTTP_404_NOT_FOUND)

        self._audit_post(AuditAction.CREATE_POST, post, {"endpoint": "POST /api/v1/posts"})
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        tags=["Posts/Share"],
        summary="리포스트(공유) 생성",
        description="해당 포스트를 내 타임라인에 리포스트로 공유합니다.",
        operation_id="posts_share",
        parameters=[OpenApiParameter(name="pk", location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="원본 포스트 ID")],
        responses={
            201: OpenApiResponse(response=RepostOut, description="생성된 리포스트"),
            400: OpenApiResponse(response=ErrorOut, description="이미 리포스트한 경우"),
            401: OpenApiResponse(response=ErrorOut),
            404: OpenApiResponse(response=ErrorOut),
        },
        examples=[
            OpenApiExample("응답 예시", value={"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "original_post_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"}, response_only=True)
        ],
    )
    # UX는 /share, 모델은 Repost
    @action(detail=True, methods=["post"], url_path="share", permission_classes=[IsAuthenticated])
    def share(self, request, pk=None):
        original = get_object_or_404(Post, pk=pk)
        try:
            with transaction.atomic():
                rp = Repost.objects.create(user=request.user, original_post=original)
        except IntegrityError:
            return Response({"detail": "Already reposted"}, status=status.HTTP_400_BAD_REQUEST)

        write_audit_log(
            action=AuditAction.REPOST_CREATE,
            user=request.user,
            target_type="post",
            target_id=str(original.id),
            request=request,
            extra={"endpoint": "POST /api/v1/posts/{id}/share", "repost_id": str(rp.id)},
        )
        return Response(RepostOut(rp).data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    list=extend_schema(
        tags=["Bookmarks"],
        summary="내 북마크 목록",
        operation_id="bookmarks_list",
        responses={200: OpenApiResponse(response=BookmarkOut(many=True)), 401: OpenApiResponse(response=ErrorOut)},
    )
)
class BookmarkViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    GET /api/v1/bookmarks/
    """

    serializer_class = BookmarkOut
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Bookmark.objects.filter(user=self.request.user).select_related("post").order_by("-created_at")
