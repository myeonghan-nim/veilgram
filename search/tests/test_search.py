import uuid

import pytest
from django.conf import settings
from django.utils import timezone
from rest_framework.test import APIClient

from search import services


# Local fixtures
@pytest.fixture(autouse=True)
def use_memory_backend(monkeypatch):
    # OpenSearch 외부 의존 끊고 InMemory 백엔드로 테스트, settings.OPENSEARCH.ENABLED = False 강제 + backend 캐시 초기화
    if not hasattr(settings, "OPENSEARCH"):
        settings.OPENSEARCH = {}

    monkeypatch.setitem(settings.OPENSEARCH, "ENABLED", False)

    # backend 싱글톤 초기화
    from search import services as sv

    sv._backend = None
    yield
    sv._backend = None


class _DummyUser:
    def __init__(self, user_id=None):
        self.id = user_id or uuid.uuid4()

    @property
    def is_authenticated(self):
        return True


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def authenticated_user():
    client = APIClient()
    client.force_authenticate(user=_DummyUser())
    return client


# Tests
@pytest.mark.django_db
class TestSearchAPI:
    def _seed_basics(self):
        b = services.backend()
        now = timezone.now()

        u1 = {"id": str(uuid.uuid4()), "nickname": "han_nim", "status_message": "안녕하세요", "created_at": now}
        u2 = {"id": str(uuid.uuid4()), "nickname": "hannah", "status_message": "backend dev", "created_at": now}
        b.bulk_index("user", [u1, u2])

        p1 = {
            "id": str(uuid.uuid4()),
            "author_id": u1["id"],
            "author_nickname": "han_nim",
            "content": "장고로 SNS 검색 만들기 #django #search",
            "hashtags": ["django", "search"],
            "created_at": now,
            "like_count": 10,
        }
        p2 = {
            "id": str(uuid.uuid4()),
            "author_id": u2["id"],
            "author_nickname": "hannah",
            "content": "OpenSearch 튜닝 팁 공유 #opensearch",
            "hashtags": ["opensearch"],
            "created_at": now,
            "like_count": 5,
        }
        b.bulk_index("post", [p1, p2])
        b.bulk_index("hashtag", [{"name": "django", "post_count": 1}, {"name": "opensearch", "post_count": 1}])

    def test_search_users_success(self, authenticated_user):
        self._seed_basics()

        r = authenticated_user.get("/api/v1/search/users/", {"q": "han", "page": 1, "size": 10})
        assert r.status_code == 200

        data = r.json()
        assert data["total"] >= 1
        assert any("han" in row["nickname"].lower() for row in data["results"])

    def test_search_posts_success_substring(self, authenticated_user):
        self._seed_basics()

        r = authenticated_user.get("/api/v1/search/posts/", {"q": "검색", "page": 1, "size": 10})
        assert r.status_code == 200

        contents = [x["content"] for x in r.json()["results"]]
        assert any("SNS 검색" in c for c in contents)

    def test_search_hashtags_success(self, authenticated_user):
        self._seed_basics()

        r = authenticated_user.get("/api/v1/search/hashtags/", {"q": "open", "page": 1, "size": 10})
        assert r.status_code == 200

        names = [x["name"] for x in r.json()["results"]]
        assert "opensearch" in names

    def test_requires_auth(self, api_client):
        r = api_client.get("/api/v1/search/users/", {"q": "a"})
        assert r.status_code in (401, 403)

    def test_validation_q_required(self, authenticated_user):
        r = authenticated_user.get("/api/v1/search/users/")  # q 누락
        assert r.status_code == 400

    def test_pagination(self, authenticated_user):
        b = services.backend()
        now = timezone.now()
        for i in range(3):
            b.index_post({"id": str(uuid.uuid4()), "author_id": str(uuid.uuid4()), "author_nickname": "x", "content": f"p{i}", "hashtags": [], "created_at": now, "like_count": 0})

        r1 = authenticated_user.get("/api/v1/search/posts/", {"q": "p", "page": 1, "size": 1})
        r2 = authenticated_user.get("/api/v1/search/posts/", {"q": "p", "page": 2, "size": 1})
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json()["results"] != r2.json()["results"]
