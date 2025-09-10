import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from relations.models import Follow
from posts.models import Post

pytestmark = pytest.mark.django_db
User = get_user_model()


# ---------- 더미 캐시 ----------
class DummyCache:
    # feed.services._cache 대체: 인메모리 캐시로 외부 Redis 의존 제거

    def __init__(self):
        self.following = {}  # (user_id, page, size) -> list[dict]
        self.hashtag = {}  # (tag, page, size) -> list[dict]

    # following
    def get_following(self, user_id, page, size):
        return self.following.get((str(user_id), page, size))

    def set_following(self, user_id, page, size, items):
        self.following[(str(user_id), page, size)] = items

    def bump_following_ver(self, user_ids):
        # 버전 키만 갱신하면 되므로 테스트에선 no-op
        pass

    # hashtag
    def get_hashtag(self, tag, page, size):
        return self.hashtag.get((tag, page, size))

    def set_hashtag(self, tag, page, size, items):
        self.hashtag[(tag, page, size)] = items

    def incr_hashtag(self, tag, score):
        pass


class BaseFeedAPITest:
    @pytest.fixture(autouse=True)
    def _env(self, settings, monkeypatch):
        # Cassandra 끔 → ORM 경로 사용
        settings.CASSANDRA_ENABLED = False
        # services 모듈의 전역 캐시를 더미로 교체
        import feed.services as services

        monkeypatch.setattr(services, "_cache", DummyCache())

    @pytest.fixture
    def users(self):
        author = User.objects.create()
        follower = User.objects.create()
        return author, follower

    @pytest.fixture
    def api(self, users):
        _, follower = users
        client = APIClient()
        client.force_authenticate(follower)
        return client


class TestFollowingAPI(BaseFeedAPITest):
    def test_following_returns_posts(self, users, api):
        author, follower = users
        Follow.objects.create(follower=follower, following=author)

        p = Post.objects.create(author=author, content="Hello")

        r = api.get("/api/v1/feed/following/?page=0&size=10")
        assert r.status_code == 200

        data = r.json()  # ViewSet은 리스트를 바로 반환
        assert isinstance(data, list)
        assert any(item["post_id"] == str(p.id) for item in data)

    def test_following_empty_without_relation(self, api):
        r = api.get("/api/v1/feed/following/?page=0&size=10")
        assert r.status_code == 200
        assert r.json() == []


class TestHashtagAPI(BaseFeedAPITest):
    def test_hashtag_endpoint_path_param(self, api):
        r = api.get("/api/v1/feed/hashtags/testtag/?page=0&size=5")
        assert r.status_code == 200
        assert r.json() == []  # repo 비활성이라 빈 리스트
