from typing import Iterable, Dict, List

from celery import shared_task
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .models import Device, Notification, NotificationSetting
from .providers import get_provider
from relations.models import Follow

User = get_user_model()

BATCH_SIZE = 500  # FCM 멀티캐스트 권장 범위에 맞춰 배치


def _chunk(seq: List[str], size: int):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def _eligible_user_ids(user_ids: Iterable[str], notif_type: str) -> List[str]:
    # 설정 필터링: 해당 타입이 True인 사용자만
    qs = NotificationSetting.objects.filter(user_id__in=user_ids)
    flag = {"post": "post", "comment": "comment", "like": "like", "follow": "follow"}[notif_type]
    allowed = [str(s.user_id) for s in qs if getattr(s, flag)]
    return allowed


@shared_task(name="notifications.tasks.fanout_post_created", autoretry_for=(Exception,), retry_backoff=2, max_retries=5)
def fanout_post_created(author_id: str, post_id: str, title: str, body: str):
    # 1) 대상 선정: author의 followers
    follower_ids = list(Follow.objects.filter(following_id=author_id).values_list("follower_id", flat=True))
    if not follower_ids:
        return 0

    # 2) 설정 필터
    user_ids = _eligible_user_ids(follower_ids, "post")
    if not user_ids:
        return 0

    # 3) 디바이스 토큰 수집
    tokens = list(Device.objects.filter(user_id__in=user_ids, is_active=True).values_list("platform", "device_token"))

    # 4) 인앱 Notification 저장 + 푸시 전송
    now = timezone.now()
    with transaction.atomic():
        Notification.objects.bulk_create(
            [Notification(user_id=uid, type=Notification.Type.POST, payload={"post_id": post_id, "author_id": author_id}, created_at=now) for uid in user_ids],
            ignore_conflicts=True,
        )

    # 5) 플랫폼별 멀티캐스트
    provider = get_provider()
    sent = 0
    for platform in ("android", "ios", "web"):
        platform_tokens = [t for p, t in tokens if p == platform]
        for batch in _chunk(platform_tokens, BATCH_SIZE):
            ok, _ = provider.send_multicast(platform=platform, tokens=batch, title=title, body=body, data={"type": "post", "post_id": post_id, "author_id": author_id})
            sent += ok
    return sent


@shared_task(name="notifications.tasks.single_user_push", autoretry_for=(Exception,), retry_backoff=2, max_retries=5)
def single_user_push(user_id: str, type_: str, title: str, body: str, data: Dict):
    # 공용 싱글 유저 태스크(댓글, 좋아요, 팔로우 등)
    # 1) 설정 필터
    if str(user_id) not in _eligible_user_ids([user_id], type_):
        return 0

    # 2) 인앱 저장
    Notification.objects.create(user_id=user_id, type=type_, payload=data)

    # 3) 푸시
    provider = get_provider()
    tokens = list(Device.objects.filter(user_id=user_id, is_active=True).values_list("platform", "device_token"))
    sent = 0
    for platform in ("android", "ios", "web"):
        platform_tokens = [t for p, t in tokens if p == platform]
        for batch in _chunk(platform_tokens, BATCH_SIZE):
            ok, _ = provider.send_multicast(platform, batch, title, body, data)
            sent += ok
    return sent
