from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied, ValidationError

from .events import emit_user_blocked, emit_user_followed, emit_user_unblocked, emit_user_unfollowed
from .models import Block, Follow

User = get_user_model()


@dataclass(frozen=True)
class RelationResult:
    changed: bool = True  # 실제 DB 변화가 있었는지 (테스트/감사 로그에 유용)


class RelationshipService:
    """
    팔로우/언팔로우, 블록/언블록의 규칙을 한 곳에서 강제.
    - 자기 자신 대상 금지
    - 차단 중에는 팔로우 불가(양방향 차단 모두 금지)
    - 블록하면 양방향 팔로우 모두 제거(피드·알림 혼선 방지)
    """

    @staticmethod
    def _validate_not_self(actor, target):
        if actor.id == target.id:
            raise ValidationError({"detail": "Cannot target yourself."})

    @staticmethod
    def _ensure_not_blocked(actor, target):
        # 나→상대 또는 상대→나 차단 중이면 팔로우 불가
        if Block.objects.filter(Q(user_id=actor.id, blocked_user_id=target.id) | Q(user_id=target.id, blocked_user_id=actor.id)).exists():
            raise PermissionDenied("Following is not allowed while blocked.")

    @staticmethod
    @transaction.atomic
    def follow(actor, target) -> RelationResult:
        RelationshipService._validate_not_self(actor, target)
        RelationshipService._ensure_not_blocked(actor, target)
        _, created = Follow.objects.get_or_create(follower=actor, following=target)
        if not created:
            raise ValidationError({"detail": "Already following."})
        emit_user_followed(actor.id, target.id)
        return RelationResult(changed=True)

    @staticmethod
    @transaction.atomic
    def unfollow(actor, target) -> RelationResult:
        RelationshipService._validate_not_self(actor, target)
        deleted, _ = Follow.objects.filter(follower=actor, following=target).delete()
        if deleted == 0:
            raise ValidationError({"detail": "Not following."})
        emit_user_unfollowed(actor.id, target.id)
        return RelationResult(changed=True)

    @staticmethod
    @transaction.atomic
    def block(actor, target) -> RelationResult:
        RelationshipService._validate_not_self(actor, target)
        _, created = Block.objects.get_or_create(user=actor, blocked_user=target)
        if not created:
            raise ValidationError({"detail": "Already blocked."})
        # 양방향 팔로우 모두 제거
        removed = list(Follow.objects.filter(Q(follower=actor, following=target) | Q(follower=target, following=actor)).values_list("follower_id", "following_id"))
        Follow.objects.filter(Q(follower=actor, following=target) | Q(follower=target, following=actor)).delete()
        emit_user_blocked(actor.id, target.id)
        # 자동 언팔로우된 관계에 대해서도 이벤트
        for f_id, g_id in removed:
            emit_user_unfollowed(f_id, g_id)
        return RelationResult(changed=True)

    @staticmethod
    @transaction.atomic
    def unblock(actor, target) -> RelationResult:
        RelationshipService._validate_not_self(actor, target)
        deleted, _ = Block.objects.filter(user=actor, blocked_user=target).delete()
        if deleted == 0:
            raise ValidationError({"detail": "Not blocked."})
        emit_user_unblocked(actor.id, target.id)
        return RelationResult(changed=True)
