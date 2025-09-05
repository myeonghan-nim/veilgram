import importlib
import sys

import pytest

from relations.models import Follow
from posts.models import Post


@pytest.mark.django_db
class TestFeedInvalidation:
    @pytest.fixture(autouse=True)
    def _fake_redis(self, monkeypatch):
        # 모든 테스트에서 Redis 클라이언트를 fakeredis로 대체한다. services 모듈이 import될 때 생성되는 _cache가 가짜 Redis를 쓰도록 from_url 자체를 패치한다.
        import fakeredis

        def _from_url(url, decode_responses=True):
            return fakeredis.FakeRedis(decode_responses=decode_responses)

        # feed.cache 내부에서 사용되는 redis.Redis.from_url만 패치
        monkeypatch.setattr("feed.cache.redis.Redis.from_url", staticmethod(_from_url), raising=True)

    @pytest.fixture
    def svc(self, settings):
        # Cassandra를 끄고 feed.services를 '패치 이후' 재임포트하여 _cache/_repo가 테스트 전용 환경을 사용하게 만든다.
        settings.CASSANDRA_ENABLED = False
        sys.modules.pop("feed.services", None)  # 강제 재임포트
        return importlib.import_module("feed.services")

    @pytest.fixture
    def users(self, django_user_model):
        author = django_user_model.objects.create()
        follower = django_user_model.objects.create()
        Follow.objects.create(follower_id=follower.id, following_id=author.id)
        return author, follower

    def test_following_feed_invalidation_and_rebuild(self, users, svc):
        author, follower = users

        # 1) 초기 조회: 캐시 미스 → 비어있음
        items = svc.fetch_following_feed(follower.id, page=0, size=10)
        assert items == []

        # 2) 작성자 A가 새 글 작성
        p = Post.objects.create(author_id=author.id, content="hello")

        # 3) PostCreated 이벤트 수신 → 팔로워 B의 following feed 버전 bump
        evt = {"type": "PostCreated", "payload": {"post_id": str(p.id), "author_id": str(author.id), "created_ms": int(p.created_at.timestamp() * 1000), "hashtags": ["hello"]}}
        svc.handle_post_created(evt)

        # 4) 다음 조회: 캐시 미스 → 재생성되어 새 포스트 포함
        items2 = svc.fetch_following_feed(follower.id, page=0, size=10)
        assert str(p.id) in [x["post_id"] for x in items2]

    def test_following_feed_second_call_is_consistent(self, users, svc):
        author, follower = users

        p = Post.objects.create(author_id=author.id, content="hello-2")
        evt = {"type": "PostCreated", "payload": {"post_id": str(p.id), "author_id": str(author.id), "created_ms": int(p.created_at.timestamp() * 1000), "hashtags": []}}
        svc.handle_post_created(evt)

        first = svc.fetch_following_feed(follower.id, page=0, size=10)
        second = svc.fetch_following_feed(follower.id, page=0, size=10)

        pid = str(p.id)
        assert pid in [x["post_id"] for x in first]
        assert first == second
