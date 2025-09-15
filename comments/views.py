from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiParameter, OpenApiResponse, OpenApiTypes, OpenApiExample
from rest_framework import mixins, viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Comment
from .permissions import IsAuthorOrReadOnly
from .serializers import CommentSerializer
from assets.models import Asset, AssetStatus
from assets.serializers import AssetOut
from posts.models import Post
from common.schema import ErrorOut, AssetIdsIn, AttachErrorsOut


@extend_schema_view(
    list=extend_schema(
        tags=["Comments"],
        summary="게시물의 최상위 댓글 목록",
        description="지정한 게시물(post_id)의 **최상위 댓글(parent is null)** 목록을 반환합니다. 페이지네이션은 전역 DRF 설정을 따릅니다.",
        operation_id="post_comments_list",
        parameters=[OpenApiParameter(name="post_id", location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="대상 게시물 ID (UUID)")],
        responses={200: OpenApiResponse(response=CommentSerializer), 401: ErrorOut, 404: ErrorOut},
    ),
    create=extend_schema(
        tags=["Comments"],
        summary="게시물에 새 댓글 작성",
        description=(
            "지정한 게시물(post_id)에 **최상위 댓글**을 작성합니다.\n"
            "필요 시 body에 `parent`를 넣어 대댓글을 만들 수 있지만, 일반적으로는 최상위 댓글을 생성합니다.\n"
            "첨부 자산은 별도 `/comments/{id}/assets` 엔드포인트로 연결하세요."
        ),
        operation_id="post_comments_create",
        parameters=[OpenApiParameter(name="post_id", location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="대상 게시물 ID (UUID)")],
        request=CommentSerializer,
        responses={201: OpenApiResponse(response=CommentSerializer, description="생성된 댓글"), 400: ErrorOut, 401: ErrorOut, 404: ErrorOut},
        examples=[OpenApiExample("요청 예시", value={"content": "좋은 글이네요!"}, request_only=True)],
    ),
)
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


@extend_schema_view(
    list=extend_schema(exclude=True),  # 필요 없다면 문서에서 숨김
    create=extend_schema(exclude=True),
    update=extend_schema(exclude=True),
    partial_update=extend_schema(
        tags=["Comments"],
        summary="댓글 수정(부분)",
        operation_id="comments_partial_update",
        request=CommentSerializer,
        responses={200: CommentSerializer, 400: ErrorOut, 401: ErrorOut, 403: ErrorOut, 404: ErrorOut},
    ),
    destroy=extend_schema(
        tags=["Comments"],
        summary="댓글 삭제",
        operation_id="comments_destroy",
        responses={204: OpenApiResponse(description="삭제 성공"), 401: ErrorOut, 403: ErrorOut, 404: ErrorOut},
    ),
    retrieve=extend_schema(
        tags=["Comments"],
        summary="댓글 단건 조회",
        operation_id="comments_retrieve",
        parameters=[OpenApiParameter(name="id", location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="댓글 ID (UUID)")],
        responses={200: CommentSerializer, 401: ErrorOut, 404: ErrorOut},
    ),
)
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

    @extend_schema(
        tags=["Comments"],
        summary="대댓글 목록/작성",
        description=(
            "**GET**: 해당 댓글의 대댓글 목록을 반환합니다(페이지네이션 적용 가능).\n"
            "**POST**: 해당 댓글에 대댓글을 작성합니다. 요청 본문은 댓글 생성과 동일하며, 서버가 `parent`를 자동 지정합니다."
        ),
        operation_id="comments_replies",
        parameters=[OpenApiParameter(name="id", location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="부모 댓글 ID (UUID)")],
        request=CommentSerializer,  # POST일 때 유효
        responses={
            200: OpenApiResponse(response=CommentSerializer, description="대댓글 목록(GET)"),
            201: OpenApiResponse(response=CommentSerializer, description="대댓글 생성(POST)"),
            400: ErrorOut,
            401: ErrorOut,
            404: ErrorOut,
        },
        examples=[OpenApiExample("대댓글 작성 예시", value={"content": "동의합니다!"}, request_only=True)],
    )
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

    @extend_schema(
        tags=["Comments"],
        summary="댓글에 자산 목록 조회/첨부",
        description=("**GET**: 댓글에 연결된 자산 목록을 반환합니다.\n" "**POST**: 자산을 댓글에 첨부합니다. 조건: 요청자 소유, `READY` 상태, 아직 post/comment에 미연결."),
        operation_id="comments_assets",
        parameters=[OpenApiParameter(name="id", location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="댓글 ID (UUID)")],
        request=AssetIdsIn,  # POST에서 사용
        responses={
            200: OpenApiResponse(response=AssetOut, description="자산 목록(GET)"),
            201: OpenApiResponse(response=AssetOut, description="첨부된 자산 목록(POST)"),
            400: OpenApiResponse(response=AttachErrorsOut, description="첨부 불가 자산들 상세"),
            401: ErrorOut,
            404: ErrorOut,
        },
        examples=[OpenApiExample("첨부 요청 예시", value={"asset_ids": ["11111111-1111-1111-1111-111111111111"]}, request_only=True)],
    )
    @action(detail=True, methods=["get", "post"], url_path="assets")
    def assets(self, request, pk=None):
        """
        GET  /api/v1/comments/{id}/assets            -> 댓글에 연결된 자산 목록
        POST /api/v1/comments/{id}/assets {asset_ids:[...]} -> 자산 첨부(여러 개)
        - 조건: 요청자 소유, READY 상태, 아직 post/comment에 미연결
        """
        comment = self.get_object()

        if request.method == "GET":
            qs = comment.assets.order_by("-created_at")
            return Response(AssetOut(qs, many=True).data, status=200)

        # POST attach
        asset_ids = request.data.get("asset_ids")
        if not isinstance(asset_ids, list) or not asset_ids:
            return Response({"asset_ids": ["This field is required and must be a non-empty list."]}, status=400)

        attachable = []
        errors = {}
        for aid in asset_ids:
            try:
                a = Asset.objects.get(id=aid, owner=request.user)
            except Asset.DoesNotExist:
                errors[str(aid)] = "Not found or not owned by you."
                continue
            if a.status != AssetStatus.READY:
                errors[str(aid)] = f"Asset status must be READY (current={a.status})."
                continue
            if a.post_id or a.comment_id:
                errors[str(aid)] = "Asset already attached."
                continue
            attachable.append(a)

        if errors:
            return Response({"errors": errors}, status=400)

        for a in attachable:
            a.comment = comment
            a.save(update_fields=["comment", "updated_at"])

        return Response(AssetOut(attachable, many=True).data, status=201)

    @extend_schema(
        tags=["Comments"],
        summary="댓글에서 자산 해제",
        operation_id="comments_detach_asset",
        parameters=[
            OpenApiParameter(name="id", location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="댓글 ID (UUID)"),
            OpenApiParameter(name="asset_id", location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="해제할 자산 ID (UUID)"),
        ],
        responses={204: OpenApiResponse(description="해제 성공"), 400: ErrorOut, 401: ErrorOut, 404: ErrorOut},
        examples=[OpenApiExample("해제 실패 예시", value={"detail": "Asset is not attached to this comment."}, response_only=True)],
    )
    @action(detail=True, methods=["delete"], url_path=r"assets/(?P<asset_id>[0-9a-f-]{36})")
    def detach_asset(self, request, pk=None, asset_id=None):
        """
        DELETE /api/v1/comments/{id}/assets/{asset_id} -> 자산 해제
        - 조건: 요청자 소유 + 현재 해당 댓글에 연결되어 있어야 함
        """
        comment = self.get_object()
        asset = get_object_or_404(Asset, id=asset_id, owner=request.user)

        if asset.comment_id != comment.id:
            return Response({"detail": "Asset is not attached to this comment."}, status=400)

        asset.comment = None
        asset.save(update_fields=["comment", "updated_at"])
        return Response(status=204)
