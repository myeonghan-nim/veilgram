from __future__ import annotations

import logging
import uuid
from typing import Dict, Iterable, List

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.conf import settings

from feed.services import handle_hashtags_extracted, handle_post_created, handle_post_deleted, handle_user_follow_changed
from relations.models import Follow

log = logging.getLogger(__name__)
_channel_layer = get_channel_layer()


def _group_name_for(user_id: uuid.UUID | str) -> str:
    # FEED_UPDATES_CHANNEL을 prefix로 사용 (예: "feed:updates:<uuidhex>")
    uid = str(user_id).replace("-", "")
    return f"{settings.FEED_UPDATES_CHANNEL}:{uid}"


def _broadcast_following(users: Iterable[uuid.UUID | str], payload: Dict):
    # Channels가 비활성인 환경(테스트 등)에서도 안전하게 no-op 처리
    if not _channel_layer:
        return
    for u in {str(x) for x in users}:
        async_to_sync(_channel_layer.group_send)(_group_name_for(u), {"type": "feed.update", "payload": payload})


def _followers_of(author_id: uuid.UUID) -> List[uuid.UUID]:
    return list(Follow.objects.filter(following_id=author_id).values_list("follower_id", flat=True))


@shared_task(name="feed.tasks.consume_post_created", autoretry_for=(Exception,), retry_backoff=2, max_retries=5)
def consume_post_created(evt: Dict):
    """
    evt = {
        "event": "PostCreated",
        "payload": {"post_id": str, "author_id": str, "created_ms": int, "hashtags": [str, ...]}
    }
    """
    handle_post_created(evt)  # 캐시 무효화, 저장소 적재, 해시태그 카운트
    try:
        author_id = uuid.UUID(evt["payload"]["author_id"])
        post_id = evt["payload"]["post_id"]
        followers = _followers_of(author_id)
        if followers:
            _broadcast_following(followers, {"event": "FeedUpdated", "post_id": post_id, "author_id": str(author_id)})
    except Exception as e:
        log.exception("WS broadcast failed for PostCreated: %s", e)


@shared_task(name="feed.tasks.consume_post_deleted", autoretry_for=(Exception,), retry_backoff=2, max_retries=5)
def consume_post_deleted(evt: Dict):
    """
    evt = {
        "event": "PostDeleted",
        "payload": {"author_id": str, "created_ms": int}
    }
    """
    handle_post_deleted(evt)
    try:
        author_id = uuid.UUID(evt["payload"]["author_id"])
        followers = _followers_of(author_id)
        if followers:
            _broadcast_following(followers, {"event": "FeedPruned"})
    except Exception as e:
        log.exception("WS broadcast failed for PostDeleted: %s", e)


@shared_task(name="feed.tasks.consume_hashtags_extracted", autoretry_for=(Exception,), retry_backoff=2, max_retries=5)
def consume_hashtags_extracted(evt: Dict):
    """
    evt = {
        "event": "HashtagsExtracted",
        "payload": {"post_id": str, "author_id": str, "created_ms": int, "hashtags": [str, ...]}
    }
    """
    handle_hashtags_extracted(evt)
    # 팔로잉 피드 변경이 아니므로 WS 브로드캐스트는 생략


@shared_task(name="feed.tasks.consume_user_follow_changed", autoretry_for=(Exception,), retry_backoff=2, max_retries=5)
def consume_user_follow_changed(evt: Dict):
    """
    evt = {
        "event": "UserFollowChanged",
        "payload": {"follower_id": str, "following_id": str, "action": "follow"|"unfollow"}
    }
    """
    handle_user_follow_changed(evt)
    try:
        follower_id = uuid.UUID(evt["payload"]["follower_id"])
        _broadcast_following([follower_id], {"event": "FollowingVersionBumped"})
    except Exception as e:
        log.exception("WS broadcast failed for UserFollowChanged: %s", e)
