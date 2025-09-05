import json
import uuid
from typing import List, Optional

import redis


class FeedCache:
    FOLLOWING_VER = "feed:following_ver:{user}"
    FOLLOWING_PAGE = "feed:following:{user}:v{ver}:p{page}:s{size}"
    HASHTAG_PAGE = "feed:hashtag:{tag}:p{page}:s{size}"
    POPULAR_PAGE = "feed:popular:{bucket}:p{page}:s{size}"
    HASHTAG_ZSET = "hashtag_counters"

    def __init__(self, url: str, ttl_sec: int = 60):
        self.r = redis.Redis.from_url(url, decode_responses=True)
        self.ttl = ttl_sec

    def _get_following_ver(self, user_id: uuid.UUID) -> int:
        k = self.FOLLOWING_VER.format(user=str(user_id))
        v = self.r.get(k)
        return int(v) if v else 1

    def bump_following_ver(self, user_ids: List[uuid.UUID]) -> None:
        pipe = self.r.pipeline()
        for uid in user_ids:
            k = self.FOLLOWING_VER.format(user=str(uid))
            # 없으면 1로 세팅한 뒤, INCR → 최소 2가 되도록 보장
            pipe.setnx(k, 1)
            pipe.incr(k)
        pipe.execute()

    def get_following(self, user_id: uuid.UUID, page: int, size: int) -> Optional[List[dict]]:
        ver = self._get_following_ver(user_id)
        k = self.FOLLOWING_PAGE.format(user=str(user_id), ver=ver, page=page, size=size)
        raw = self.r.get(k)
        return json.loads(raw) if raw else None

    def set_following(self, user_id: uuid.UUID, page: int, size: int, posts: List[dict]) -> None:
        ver = self._get_following_ver(user_id)
        k = self.FOLLOWING_PAGE.format(user=str(user_id), ver=ver, page=page, size=size)
        self.r.setex(k, self.ttl, json.dumps(posts))

    def get_hashtag(self, tag: str, page: int, size: int) -> Optional[List[dict]]:
        k = self.HASHTAG_PAGE.format(tag=tag, page=page, size=size)
        raw = self.r.get(k)
        return json.loads(raw) if raw else None

    def set_hashtag(self, tag: str, page: int, size: int, posts: List[dict]) -> None:
        k = self.HASHTAG_PAGE.format(tag=tag, page=page, size=size)
        self.r.setex(k, self.ttl, json.dumps(posts))

    def incr_hashtag(self, tag: str, inc: float = 1.0) -> None:
        self.r.zincrby(self.HASHTAG_ZSET, inc, tag)
