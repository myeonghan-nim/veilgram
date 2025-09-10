import json
import logging
import uuid
from typing import Any, Dict, List

import feed.event_dispather as disp
from feed.broadcast import broadcast_user_feed
from relations.models import Follow

log = logging.getLogger(__name__)
REQUIRED_KEYS = ("type", "payload")


def _parse_message(raw: bytes | str) -> Dict[str, Any]:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    obj = json.loads(raw)
    missing = [k for k in REQUIRED_KEYS if k not in obj]
    if missing:
        raise ValueError(f"invalid event: missing keys {missing}")
    return obj


def _followers_of(author_id: uuid.UUID) -> List[str]:
    return list(Follow.objects.filter(following_id=author_id).values_list("follower_id", flat=True))


def _maybe_broadcast(evt: Dict[str, Any]) -> None:
    """
    서비스 처리(캐시/저장소) 이후, 실시간 알림이 필요한 이벤트만 브로드캐스트.
    - PostCreated → 팔로워에게 "새 피드 있음"
    - PostDeleted → 팔로워에게 "피드 정리됨"
    - HashtagsExtracted/UserFollowed/UserUnfollowed → 피드 구조 직접 변화 X → 생략
    """
    t = evt.get("type")
    p = evt.get("payload") or {}
    try:
        if t == "PostCreated":
            author_id = uuid.UUID(p["author_id"])
            followers = _followers_of(author_id)
            if followers:
                broadcast_user_feed(followers, {"kind": "FeedUpdated", "post_id": p["post_id"], "author_id": str(author_id)})
        elif t == "PostDeleted":
            author_id = uuid.UUID(p["author_id"])
            followers = _followers_of(author_id)
            if followers:
                broadcast_user_feed(
                    followers,
                    {"kind": "FeedPruned"},
                )
        # HashtagsExtracted, UserFollowed, UserUnfollowed 은 브로드캐스트 생략(선택적으로 추가 가능)
    except Exception:
        log.exception("broadcast failed for evt=%s", t)


def handle_message(raw: bytes | str) -> None:
    """
    공통 진입점: raw → evt(dict) → dispatch(evt) → (옵션) 브로드캐스트
    - dispatch(evt)는 feed.services.* 핸들러를 호출.
    - 브로드캐스트는 컨슈머(realtime/consumers.py)의 계약에 맞게 전송.
    """
    evt = _parse_message(raw)
    try:
        disp.dispatch(evt)  # 서비스 처리
        _maybe_broadcast(evt)  # 실시간 알림
    except Exception:
        log.exception("dispatch/maybe_broadcast failed for evt=%s", evt.get("type"))
