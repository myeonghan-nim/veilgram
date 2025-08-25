import uuid

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from assets.models import Asset, AssetStatus
from polls.models import PollOption, Vote
from polls.services import create_poll
from posts.models import Post

pytestmark = pytest.mark.django_db


# ---------- Fixtures ----------
@pytest.fixture
def user():
    U = get_user_model()
    return U.objects.create(id=uuid.uuid4())


@pytest.fixture
def other_user():
    U = get_user_model()
    return U.objects.create(id=uuid.uuid4())


@pytest.fixture
def auth_client(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def other_client(other_user):
    c = APIClient()
    c.force_authenticate(other_user)
    return c


@pytest.fixture
def anon_client():
    return APIClient()


def _mk_ready_asset(owner, *, ext="png", content_type="image/png"):
    return Asset.objects.create(
        owner=owner,
        type="image",
        content_type=content_type,
        size_bytes=1234,
        storage_key=f"assets/test/{uuid.uuid4()}.{ext}",
        public_url=f"http://cdn.example/{uuid.uuid4()}.{ext}",
        status=AssetStatus.READY,
    )


# ---------- Retrieve Detailed ----------
class TestRetrieveDetail:
    def test_retrieve_content_only_success(self, auth_client, user):
        p = Post.objects.create(author=user, content="only text")
        r = auth_client.get(reverse("posts-detail", args=[p.id]))
        assert r.status_code == 200

        body = r.json()
        assert body["id"] == str(p.id)
        assert body["author"] == str(user.id)
        assert body["content"] == "only text"
        assert body["assets"] == []
        assert body["poll"] is None

    def test_retrieve_not_found(self, auth_client):
        r = auth_client.get(reverse("posts-detail", args=[uuid.uuid4()]))
        assert r.status_code == 404

    def test_retrieve_requires_auth(self, anon_client, user):
        p = Post.objects.create(author=user, content="x")
        r = anon_client.get(reverse("posts-detail", args=[p.id]))
        assert r.status_code in (401, 403)


# ---------- Poll: my_option ID ----------
class TestPollMyOptionId:
    def test_my_option_none_when_not_voted(self, auth_client, user):
        created = create_poll(owner=user, option_texts=["A", "B"])
        poll = created.poll
        p = Post.objects.create(author=user, content="hello", poll=poll)

        r = auth_client.get(reverse("posts-detail", args=[p.id]))
        assert r.status_code == 200
        assert r.json()["poll"]["my_option_id"] is None

    def test_my_option_ignored_when_other_voted(self, auth_client, other_user, user):
        created = create_poll(owner=user, option_texts=["A", "B"])
        poll = created.poll
        opt0 = poll.options.order_by("position").first()
        p = Post.objects.create(author=user, content="hello", poll=poll)

        # 다른 사용자가 투표
        Vote.objects.create(voter=other_user, poll=poll, option=opt0)
        PollOption.objects.filter(pk=opt0.id).update(vote_count=1)

        r = auth_client.get(reverse("posts-detail", args=[p.id]))
        assert r.status_code == 200
        assert r.json()["poll"]["my_option_id"] is None  # 내 표 아님


# ---------- Timeline Detailed ----------
class TestTimelineList:
    def test_default_returns_my_posts_only(self, auth_client, user, other_user):
        p_me = Post.objects.create(author=user, content="mine")
        p_oth = Post.objects.create(author=other_user, content="theirs")

        r = auth_client.get(reverse("posts-list"))
        assert r.status_code == 200

        ids = [x["id"] for x in r.json()["results"]]
        assert str(p_me.id) in ids and str(p_oth.id) not in ids

    def test_filter_by_author_id_valid(self, auth_client, user, other_user):
        # 각각 1개씩 생성
        p_me = Post.objects.create(author=user, content="mine")
        p_oth = Post.objects.create(author=other_user, content="theirs")

        r = auth_client.get(reverse("posts-list"), {"author_id": str(other_user.id)})
        assert r.status_code == 200

        ids = [x["id"] for x in r.json()["results"]]
        assert str(p_oth.id) in ids and str(p_me.id) not in ids

    def test_filter_by_author_id_invalid_uuid_400(self, auth_client):
        r = auth_client.get(reverse("posts-list"), {"author_id": "not-a-uuid"})
        assert r.status_code == 400
        assert b"Invalid UUID" in r.content

    def test_invalid_cursor_404(self, auth_client):
        r = auth_client.get(reverse("posts-list"), {"cursor": "invalid-cursor"})
        # DRF CursorPagination는 invalid cursor를 NotFound(404)로 응답
        assert r.status_code == 404

    def test_page_size_capped_to_100(self, auth_client, user):
        for i in range(120):
            Post.objects.create(author=user, content=f"p{i}")
        r = auth_client.get(reverse("posts-list"), {"page_size": 1000})
        assert r.status_code == 200
        assert len(r.json()["results"]) == 100
        assert r.json()["next"] is not None  # 다음 페이지 존재

    def test_empty_feed_ok(self, auth_client):
        r = auth_client.get(reverse("posts-list"))
        assert r.status_code == 200
        assert r.json()["results"] == []


# ---------- Posts with assets Detailed ----------
class TestAssetsInDetail:
    def test_assets_are_included(self, auth_client, user):
        a1 = _mk_ready_asset(user)
        a2 = _mk_ready_asset(user, ext="jpg", content_type="image/jpeg")
        p = Post.objects.create(author=user, content="with assets")
        # 서비스는 update로 연결하지만 테스트에선 직접 연결
        Asset.objects.filter(pk__in=[a1.id, a2.id]).update(post=p)

        r = auth_client.get(reverse("posts-detail", args=[p.id]))
        assert r.status_code == 200

        assets = r.json()["assets"]
        assert len(assets) == 2

        # 필수 필드 존재 여부 체크
        for item in assets:
            assert {"id", "type", "content_type", "size_bytes", "public_url", "status", "created_at"} <= set(item.keys())
