from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Exists, OuterRef
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Profile
from .serializers import ProfileReadSerializer, ProfileCreateSerializer, ProfileUpdateSerializer
from .permissions import IsOwnerOrReadOnlyProfile
from .services.validators import ForbiddenNicknameService, normalize_nickname
from relations.models import Follow, Block

User = get_user_model()


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

    @action(detail=False, methods=["get"], url_path="me", permission_classes=[IsAuthenticated])
    def me(self, request):
        prof = get_object_or_404(Profile, user=request.user)
        return Response(ProfileReadSerializer(prof).data)

    @me.mapping.patch
    def partial_update_me(self, request):
        prof = get_object_or_404(Profile, user=request.user)
        s = ProfileUpdateSerializer(prof, data=request.data, partial=True, context={"request": request})
        s.is_valid(raise_exception=True)
        obj = s.save()
        return Response(ProfileReadSerializer(obj).data)

    @me.mapping.delete
    def delete_me(self, request):
        prof = get_object_or_404(Profile, user=request.user)
        prof.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

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
