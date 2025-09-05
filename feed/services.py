import uuid
from typing import List, Dict, Optional

from django.conf import settings

from feed.cache import FeedCache
from relations.models import Follow
from posts.models import Post

_cache = FeedCache(settings.FEED_REDIS_URL, settings.FEED_CACHE_TTL_SEC)

# ---- Cassandra 지연 초기화 ----
_REPO_SENTINEL = object()
_repo: Optional[object] = _REPO_SENTINEL


def _get_repo():
    # Cassandra 리포지토리를 '처음 필요할 때' 생성, 실패하면 None으로 고정해서 Postgres fallback을 사용
    global _repo
    if _repo is _REPO_SENTINEL:
        if not settings.CASSANDRA_ENABLED:
            _repo = None
            return _repo
        try:
            from feed.cassandra_repo import CassandraRepo

            _repo = CassandraRepo(settings.CASSANDRA_CONTACT_POINTS, settings.CASSANDRA_KEYSPACE)
        except Exception:
            # 운영에선 로깅 권장: logger.exception("Cassandra init failed")
            _repo = None
    return _repo


def _followers_of(author_id: uuid.UUID) -> List[uuid.UUID]:
    return list(Follow.objects.filter(following_id=author_id).values_list("follower_id", flat=True))


def handle_post_created(evt: Dict):
    p = evt["payload"]
    post_id = uuid.UUID(p["post_id"])
    author_id = uuid.UUID(p["author_id"])
    created_ms = int(p["created_ms"])
    hashtags = p.get("hashtags", [])

    repo = _get_repo()
    if repo:
        repo.insert_post(author_id, post_id, created_ms)
        for tag in hashtags:
            repo.insert_hashtag_post(tag, post_id, author_id, created_ms)

    for tag in hashtags:
        _cache.incr_hashtag(tag, 1.0)

    followers = _followers_of(author_id)
    if followers:
        _cache.bump_following_ver(followers)


def handle_post_deleted(evt: Dict):
    p = evt["payload"]
    author_id = uuid.UUID(p["author_id"])
    created_ms = int(p["created_ms"])

    repo = _get_repo()
    if repo:
        repo.delete_post(author_id, created_ms)

    followers = _followers_of(author_id)
    if followers:
        _cache.bump_following_ver(followers)


def handle_hashtags_extracted(evt: Dict):
    p = evt["payload"]
    post_id = uuid.UUID(p["post_id"])
    author_id = uuid.UUID(p["author_id"])
    created_ms = int(p["created_ms"])
    tags = p.get("hashtags", [])

    repo = _get_repo()
    if repo:
        for t in tags:
            repo.insert_hashtag_post(t, post_id, author_id, created_ms)
            _cache.incr_hashtag(t, 1.0)


def handle_user_follow_changed(evt: Dict):
    p = evt["payload"]
    follower_id = uuid.UUID(p["follower_id"])
    _cache.bump_following_ver([follower_id])


def fetch_following_feed(user_id: uuid.UUID, page: int, size: int) -> List[Dict]:
    cached = _cache.get_following(user_id, page, size)
    if cached is not None:
        return cached

    author_ids = list(Follow.objects.filter(follower_id=user_id).values_list("following_id", flat=True))

    repo = _get_repo()
    if repo:
        posts = repo.query_following_posts(author_ids, page, size)
    else:
        qs = Post.objects.filter(author_id__in=author_ids).order_by("-created_at")[(page * size) : (page * size + size)]
        posts = [{"post_id": str(p.id), "author_id": str(p.author_id), "created_at": p.created_at.isoformat()} for p in qs]

    _cache.set_following(user_id, page, size, posts)
    return posts


def fetch_hashtag_feed(tag: str, page: int, size: int) -> List[Dict]:
    cached = _cache.get_hashtag(tag, page, size)
    if cached is not None:
        return cached

    repo = _get_repo()
    posts = repo.query_hashtag_posts(tag, page, size) if repo else []
    _cache.set_hashtag(tag, page, size, posts)
    return posts
