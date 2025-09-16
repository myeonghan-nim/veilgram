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


def _mk_ready_asset(owner, *, ext="png", content_type="image/png"):
    return Asset.objects.create(
        owner=owner,
        type="image",
        content_type=content_type,
        size_bytes=1234,
        storage_key=f"assets/test/{uuid.uuid4()}.{ext}",
        public_url=f"http://minio/x/{uuid.uuid4()}.{ext}",
        status=AssetStatus.READY,
    )


# ---------- Test: Retrieve ----------
class TestPostRetrieve:
    def test_retrieve_with_assets_and_poll_and_my_vote(self, auth_client, user):
        # 1) poll 생성 + 옵션 확보
        created = create_poll(owner=user, option_texts=["A", "B"])
        poll = created.poll
        opt_a = poll.options.order_by("position").first()

        # 2) asset 만들고 post 생성 서비스 경유
        a1 = _mk_ready_asset(user)
        # post 생성은 API로 해도 되지만 속도를 위해 직접 모델로 구성 후 연결
        p = Post.objects.create(author=user, content="hello", poll=poll)
        Asset.objects.filter(pk=a1.id).update(post=p)

        # 3) 내가 투표
        Vote.objects.create(voter=user, poll=poll, option=opt_a)
        # 옵션 카운트 수동 반영(서비스 경유가 아니므로)
        PollOption.objects.filter(pk=opt_a.id).update(vote_count=1)

        # 4) 조회
        url = reverse("posts-detail", args=[p.id])
        res = auth_client.get(url)
        assert res.status_code == 200

        body = res.json()
        assert body["id"] == str(p.id)
        assert body["author"] == str(user.id)
        assert body["content"] == "hello"
        assert len(body["assets"]) == 1
        assert body["poll"]["id"] == str(poll.id)
        assert body["poll"]["my_option_id"] == str(opt_a.id)
        assert body["poll"]["options"][0]["vote_count"] >= 1


# ---------- Test: List(Timeline) ----------
class TestPostList:
    def test_list_my_timeline_cursor(self, auth_client, user):
        # 내 글 25개 생성(커서 페이징 검증)
        _ = [Post.objects.create(author=user, content=f"p{i}") for i in range(25)]
        url = reverse("posts-list")

        # page1
        r1 = auth_client.get(url, {"page_size": 10})
        assert r1.status_code == 200

        j1 = r1.json()
        assert len(j1["results"]) == 10
        assert j1["next"]  # 커서 존재

        # page2
        r2 = auth_client.get(j1["next"])
        j2 = r2.json()
        assert len(j2["results"]) == 10
        assert j2["next"]

        # page3
        r3 = auth_client.get(j2["next"])
        j3 = r3.json()
        assert len(j3["results"]) == 5
        assert j3["next"] is None

    def test_list_by_author_filter(self, auth_client, user, other_user):
        # 서로 다른 작성자의 글
        p1 = Post.objects.create(author=user, content="mine")
        p2 = Post.objects.create(author=other_user, content="theirs")

        url = reverse("posts-list")
        # 기본: 내 글만
        r_me = auth_client.get(url)
        assert r_me.status_code == 200

        ids = [x["id"] for x in r_me.json()["results"]]
        assert str(p1.id) in ids and str(p2.id) not in ids

        # author_id=other_user
        r_oth = auth_client.get(url, {"author_id": str(other_user.id)})
        ids2 = [x["id"] for x in r_oth.json()["results"]]
        assert str(p2.id) in ids2 and str(p1.id) not in ids2
