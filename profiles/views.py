from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Exists, OuterRef
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, OpenApiTypes, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.schema import AvailabilityOut, ErrorOut
from relations.models import Block, Follow

from .models import Profile
from .permissions import IsOwnerOrReadOnlyProfile
from .serializers import ProfileCreateSerializer, ProfileReadSerializer, ProfileUpdateSerializer
from .services.validators import ForbiddenNicknameService, normalize_nickname

User = get_user_model()


@extend_schema_view(
    create=extend_schema(
        tags=["Profiles"],
        summary="프로필 생성",
        description="신규 사용자의 프로필을 생성합니다.",
        operation_id="profiles_create",
        request=ProfileCreateSerializer,
        responses={
            201: OpenApiResponse(response=ProfileReadSerializer, description="생성된 프로필"),
            400: OpenApiResponse(response=ErrorOut),
            401: OpenApiResponse(response=ErrorOut),
        },
        examples=[OpenApiExample("요청 예시", value={"nickname": "veil_user", "status_message": "hi!"}, request_only=True)],
    ),
    retrieve=extend_schema(
        tags=["Profiles"],
        summary="프로필 단건 조회",
        operation_id="profiles_retrieve",
        parameters=[OpenApiParameter(name="user_id", location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="대상 사용자 ID (UUID). lookup_field=user_id")],
        responses={200: OpenApiResponse(response=ProfileReadSerializer), 401: OpenApiResponse(response=ErrorOut), 404: OpenApiResponse(response=ErrorOut)},
    ),
)
class ProfileViewSet(viewsets.GenericViewSet, mixins.CreateModelMixin, mixins.RetrieveModelMixin):
    queryset = Profile.objects.select_related("user")
    serializer_class = ProfileReadSerializer
    permission_classes = [IsOwnerOrReadOnlyProfile]
    lookup_field = "user_id"

    def get_queryset(self):
        qs = Profile.objects.select_related("user").annotate(follower_count=Count("user__followers", distinct=True), following_count=Count("user__following", distinct=True))

        user = getattr(self.request, "user", None)
        if user and user.is_authenticated:
            qs = qs.annotate(
                is_following=Exists(Follow.objects.filter(follower_id=user.id, following_id=OuterRef("user_id"))),
                is_followed_by=Exists(Follow.objects.filter(follower_id=OuterRef("user_id"), following_id=user.id)),
                is_blocked_by_me=Exists(Block.objects.filter(user_id=user.id, blocked_user_id=OuterRef("user_id"))),
                has_blocked_me=Exists(Block.objects.filter(user_id=OuterRef("user_id"), blocked_user_id=user.id)),
            )
        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return ProfileCreateSerializer
        if self.action in ("partial_update_me", "update_me", "me"):
            return ProfileUpdateSerializer if self.request.method != "GET" else ProfileReadSerializer
        return ProfileReadSerializer

    def perform_create(self, serializer):
        obj = serializer.save()

        def _index():
            # 지연 import로 테스트/로딩 시 의존성 최소화
            from search.services import index_user

            index_user(user_id=obj.user_id, nickname=obj.nickname, status_message=getattr(obj, "status_message", "") or "", created_at=obj.created_at)

        transaction.on_commit(_index)

    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=["Profiles"],
        summary="내 프로필 조회",
        operation_id="profiles_me_get",
        responses={200: OpenApiResponse(response=ProfileReadSerializer), 401: OpenApiResponse(response=ErrorOut)},
    )
    @action(detail=False, methods=["get"], url_path="me", permission_classes=[IsAuthenticated])
    def me(self, request):
        prof = get_object_or_404(Profile, user=request.user)
        return Response(ProfileReadSerializer(prof).data)

    @extend_schema(
        tags=["Profiles"],
        summary="내 프로필 수정(부분)",
        operation_id="profiles_me_patch",
        request=ProfileUpdateSerializer,
        responses={200: OpenApiResponse(response=ProfileReadSerializer), 400: OpenApiResponse(response=ErrorOut), 401: OpenApiResponse(response=ErrorOut)},
        examples=[OpenApiExample("요청 예시", value={"status_message": "updated!"}, request_only=True)],
    )
    @me.mapping.patch
    def partial_update_me(self, request):
        prof = get_object_or_404(Profile, user=request.user)
        s = ProfileUpdateSerializer(prof, data=request.data, partial=True, context={"request": request})
        s.is_valid(raise_exception=True)
        obj = s.save()
        return Response(ProfileReadSerializer(obj).data)

    @extend_schema(
        tags=["Profiles"],
        summary="내 프로필 삭제",
        operation_id="profiles_me_delete",
        responses={204: OpenApiResponse(description="삭제 성공"), 401: OpenApiResponse(response=ErrorOut)},
    )
    @me.mapping.delete
    def delete_me(self, request):
        prof = get_object_or_404(Profile, user=request.user)
        prof.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        tags=["Profiles"],
        summary="닉네임 가용성 점검",
        description=(
            "`nickname` 후보의 사용 가능 여부를 검사합니다.\n"
            "- 길이/형식 검사, 금칙어 포함 여부, 중복 여부를 판단합니다.\n"
            "- `reasons` 예: `Type Error(Length)`, `Type Error(Format)`, `Forbidden Word Included`, `Duplicate Nickname`"
        ),
        operation_id="profiles_availability",
        parameters=[
            OpenApiParameter(
                name="nickname", location=OpenApiParameter.QUERY, required=False, type=OpenApiTypes.STR, description="가용성 검사할 닉네임(미지정 시 빈 문자열로 처리)"
            )
        ],
        responses={200: OpenApiResponse(response=AvailabilityOut, description="가용성 결과"), 401: OpenApiResponse(response=ErrorOut)},
        examples=[
            OpenApiExample("예시", value=None, request_only=True, description="GET /api/v1/profiles/availability?nickname=veil_user"),
            OpenApiExample("응답 예시", value={"nickname": "veil_user", "available": True, "reasons": []}, response_only=True),
        ],
    )
    @action(detail=False, methods=["get"], url_path="availability", permission_classes=[IsAuthenticated])
    def availability(self, request):
        nickname = request.query_params.get("nickname") or ""
        reasons = []
        candidate = normalize_nickname(nickname)
        if not candidate or not (2 <= len(candidate) <= 20):
            reasons.append("Type Error(Length)")

        from .services.validators import NICKNAME_REGEX

        if not NICKNAME_REGEX.match(candidate):
            reasons.append("Type Error(Format)")
        words = ForbiddenNicknameService.load()
        if candidate.lower() in words or any(w in candidate.lower() for w in words):
            reasons.append("Forbidden Word Included")
        exists = Profile.objects.filter(nickname__iexact=candidate).exists()
        if exists:
            reasons.append("Duplicate Nickname")
        return Response({"nickname": candidate, "available": len(reasons) == 0, "reasons": reasons})
