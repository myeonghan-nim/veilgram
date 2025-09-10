from __future__ import annotations

import inspect
from typing import Iterable, Dict

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from realtime.groups import user_feed_group


def broadcast_user_feed(user_ids: Iterable[str | bytes], payload: Dict):
    """
    Feed 업데이트를 구독 중인 사용자 그룹으로 브로드캐스트.
    - 그룹명: user_feed_group(user_id)
    - 메시지 타입: "feed.update"  (컨슈머의 feed_update 핸들러와 매칭)
    - payload 구조는 자유. 컨슈머는 {"event":"feed_update","data":payload}로 전달.
    """
    layer = get_channel_layer()
    if not layer:
        return

    send = layer.group_send
    is_async = inspect.iscoroutinefunction(send)
    for uid in {str(u) for u in user_ids}:
        group = user_feed_group(uid)
        msg = {"type": "feed.update", "payload": payload}
        if is_async:
            async_to_sync(send)(group, msg)
        else:
            # 테스트 더미가 동기 구현인 경우 방어
            send(group, msg)
