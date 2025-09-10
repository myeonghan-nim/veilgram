from __future__ import annotations
import datetime as dt
from typing import Dict, Any, Iterable

from . import services


def _iso_from_ms(ms: int) -> str:
    # ms epoch → ISO8601 (UTC)
    return dt.datetime.utcfromtimestamp(ms / 1000.0).replace(tzinfo=dt.timezone.utc).isoformat()


def _list(value) -> Iterable:
    if not value:
        return []
    return value if isinstance(value, (list, tuple)) else [value]


def dispatch(evt: Dict[str, Any]) -> None:
    t = evt.get("type")
    p = evt.get("payload") or {}

    if t == "PostCreated":
        services.index_post(
            post_id=p["post_id"],
            author_id=p["author_id"],
            author_nickname=p.get("author_nickname", ""),
            content=p.get("content", ""),
            hashtags=_list(p.get("hashtags", [])),
            created_at=_iso_from_ms(int(p["created_ms"])) if "created_ms" in p else p.get("created_at"),
            like_count=int(p.get("like_count", 0)),
        )
    elif t == "PostDeleted":
        services.delete_post(p["post_id"])

    elif t == "HashtagsExtracted":
        # 여러 태그가 올 수도 있음
        tags = _list(p.get("hashtags", []))
        for name in tags:
            services.index_hashtag(name=name, post_count=int(p.get("post_count", 0)))

    elif t in ("UserCreated", "UserUpdated"):
        services.index_user(
            user_id=p["user_id"],
            nickname=p.get("nickname", ""),
            status_message=p.get("status_message", ""),
            created_at=p.get("created_at") or _iso_from_ms(int(p["created_ms"])) if "created_ms" in p else None,
        )
    elif t == "UserDeleted":
        services.delete_user(p["user_id"])

    # 기타 이벤트는 무시 (검색과 무관)
