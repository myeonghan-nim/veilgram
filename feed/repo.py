"""
Feed 저장소 추상화.
- 운영: Cassandra(주어진 cassandra_repo.py 래핑)
- 로컬/테스트: Django ORM로 동등 시맨틱 제공

왜 이렇게?
- cassandra_repo는 per-author 파티션에 write하고, read 시 여러 author 파티션을 merge → 대규모 팔로잉 피드에 적합.
- 서비스 계층은 저장소 디테일을 몰라도 되도록 통일 인터페이스 제공.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Dict, List

from django.conf import settings
from django.utils import timezone

# ---------- 공용 타입 ----------
FeedRow = Dict[str, str]  # {"post_id": "...", "author_id": "...", "created_at": "..."}


def _to_uuid(v) -> uuid.UUID:
    return v if isinstance(v, uuid.UUID) else uuid.UUID(str(v))


def _to_ms(ts: dt.datetime) -> int:
    if ts.tzinfo is None:
        ts = timezone.make_aware(ts, timezone=timezone.utc)
    return int(ts.timestamp() * 1000)


# ---------- 추상 인터페이스 ----------
class BaseFeedRepo:
    def insert_post(self, author_id: uuid.UUID | str, post_id: uuid.UUID | str, created_at: dt.datetime, like_count: int = 0, comment_count: int = 0) -> None: ...
    def delete_post(self, author_id: uuid.UUID | str, created_at: dt.datetime) -> None: ...
    def insert_hashtag_post(self, tag: str, post_id: uuid.UUID | str, author_id: uuid.UUID | str, created_at: dt.datetime) -> None: ...
    def query_following_posts(self, author_ids: List[uuid.UUID | str], page: int, size: int) -> List[FeedRow]: ...
    def query_hashtag_posts(self, tag: str, page: int, size: int) -> List[FeedRow]: ...


# ---------- Cassandra 백엔드 (주어진 구현을 래핑) ----------
class CassandraFeedRepo(BaseFeedRepo):
    """
    내부적으로 cassandra_repo.CassandraRepo를 사용.
    테이블/키스페이스 정의는 deploy/cassandra/feed.cql에 있음.
    """

    def __init__(self):
        from .cassandra_repo import CassandraRepo  # 주어진 파일

        contact_points = getattr(settings, "CASSANDRA_CONTACT_POINTS", ["cassandra"])
        keyspace = getattr(settings, "CASSANDRA_KEYSPACE", "veilgram")
        self.client = CassandraRepo(contact_points, keyspace)

    def insert_post(self, author_id, post_id, created_at, like_count=0, comment_count=0):
        self.client.insert_post(author_id=_to_uuid(author_id), post_id=_to_uuid(post_id), created_ms=_to_ms(created_at), like_count=like_count, comment_count=comment_count)

    def delete_post(self, author_id, created_at):
        # 주어진 API는 created_ms 기반 삭제(timeuuid 키 필요)
        self.client.delete_post(author_id=_to_uuid(author_id), created_ms=_to_ms(created_at))

    def insert_hashtag_post(self, tag, post_id, author_id, created_at):
        self.client.insert_hashtag_post(tag=tag, post_id=_to_uuid(post_id), author_id=_to_uuid(author_id), created_ms=_to_ms(created_at))

    def query_following_posts(self, author_ids, page, size):
        return self.client.query_following_posts(author_ids=[_to_uuid(a) for a in author_ids], page=page, size=size)

    def query_hashtag_posts(self, tag, page, size):
        return self.client.query_hashtag_posts(tag=tag, page=page, size=size)


# ---------- Django ORM 백엔드 (로컬/테스트 용) ----------
class DjangoFeedRepo(BaseFeedRepo):
    """
    카산드라 시맨틱을 ORM으로 근사:
    - insert_post: posts.Post의 존재를 전제로 '있다고 가정'하고 no-op (작성 시점은 Post가 DB에 이미 기록됨)
        → 필요하면 별도 FeedAuthorPost 테이블로 materialize 가능.
    - delete_post: no-op (작성과 동일한 이유; 테스트 일관성 유지를 위해 보수적으로 동작)
    - query_following_posts: 팔로우 중인 author들의 Post를 병합 정렬하여 페이지네이션
    - query_hashtag_posts: 해시태그 인덱싱이 있으면 사용, 없으면 빈 결과
    """

    def __init__(self):
        from posts.models import Post  # 게시글 소스

        self.Post = Post
        # 선택: 해시태그 연동(있으면 사용)
        try:
            from hashtags.models import PostHashtag

            self.PostHashtag = PostHashtag
        except Exception:
            self.PostHashtag = None

    def insert_post(self, author_id, post_id, created_at, like_count=0, comment_count=0):
        # ORM 백엔드는 Post가 이미 존재하므로 별도 적재가 필요없다.
        return None

    def delete_post(self, author_id, created_at):
        return None

    def insert_hashtag_post(self, tag, post_id, author_id, created_at):
        # 해시태그 인덱스 테이블이 있으면 기록, 없으면 무시
        if self.PostHashtag:
            try:
                self.PostHashtag.objects.get_or_create(hashtag=tag, post_id=_to_uuid(post_id), defaults={"author_id": _to_uuid(author_id), "created_at": created_at})
            except Exception:
                pass

    def query_following_posts(self, author_ids, page, size):
        if not author_ids:
            return []
        qs = self.Post.objects.filter(author_id__in=[_to_uuid(a) for a in author_ids]).order_by("-created_at", "-id")
        start = page * size
        rows = list(qs[start : start + size])
        return [{"post_id": str(r.id), "author_id": str(r.author_id), "created_at": r.created_at.isoformat()} for r in rows]

    def query_hashtag_posts(self, tag, page, size):
        if not self.PostHashtag:
            return []
        qs = self.PostHashtag.objects.filter(hashtag=tag).order_by("-created_at")
        start = page * size
        rows = list(qs[start : start + size])
        return [{"post_id": str(r.post_id), "author_id": str(r.author_id), "created_at": r.created_at.isoformat()} for r in rows]


# ---------- 팩토리 ----------
def get_repo() -> BaseFeedRepo:
    """
    settings.CASSANDRA_ENABLED 플래그를 그대로 따름.
    - True  → CassandraFeedRepo
    - False → DjangoFeedRepo
    """
    return CassandraFeedRepo() if getattr(settings, "CASSANDRA_ENABLED", False) else DjangoFeedRepo()
