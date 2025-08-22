import uuid

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from assets.models import Asset, AssetStatus
from polls.services import create_poll as svc_create_poll
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
    a = Asset.objects.create(
        owner=owner,
        type="image" if content_type.startswith("image/") else "video",
        content_type=content_type,
        size_bytes=1234,
        storage_key=f"assets/test/{uuid.uuid4()}.{ext}",
        public_url=f"http://minio.local/media/{uuid.uuid4()}.{ext}",
        status=AssetStatus.READY,
    )
    return a


# ---------- Test: Success ----------


class TestCreatePostSuccess:
    def test_create_with_content_only(self, auth_client, user):
        url = reverse("posts-list")
        res = auth_client.post(url, data={"content": "hello world"}, format="json")
        assert res.status_code == 201

        body = res.json()
        assert "id" in body and "author" in body and "created_at" in body

        p = Post.objects.get(id=body["id"])
        assert p.author_id == user.id and p.poll_id is None

    def test_create_with_assets(self, auth_client, user):
        a1 = _mk_ready_asset(user)
        a2 = _mk_ready_asset(user, ext="jpg", content_type="image/jpeg")

        url = reverse("posts-list")
        res = auth_client.post(url, data={"content": "with assets", "asset_ids": [str(a1.id), str(a2.id)]}, format="json")
        assert res.status_code == 201

        pid = uuid.UUID(res.json()["id"])
        # 자산이 포스트에 연결되었는지 확인
        a1.refresh_from_db()
        a2.refresh_from_db()
        assert a1.post_id == pid and a2.post_id == pid

    def test_create_with_poll_id(self, auth_client, user):
        created = svc_create_poll(owner=user, option_texts=["A", "B"])
        poll = created.poll
        url = reverse("posts-list")
        res = auth_client.post(url, data={"content": "with poll", "poll_id": str(poll.id)}, format="json")
        assert res.status_code == 201

        p = Post.objects.get(id=res.json()["id"])
        assert p.poll_id == poll.id

    def test_create_with_poll_options_instant_create(self, auth_client, user):
        url = reverse("posts-list")
        payload = {"content": "with new poll", "poll": {"options": ["A", "B"], "allow_multiple": False}}
        res = auth_client.post(url, data=payload, format="json")
        assert res.status_code == 201

        p = Post.objects.get(id=res.json()["id"])
        assert p.poll_id is not None  # 즉석 생성 Poll 연결됨


# ---------- Test: Fail ----------


class TestCreatePostValidation:
    def test_reject_empty_content(self, auth_client):
        url = reverse("posts-list")
        res = auth_client.post(url, data={"content": "   "}, format="json")
        assert res.status_code == 400
        assert b"Content must not be empty" in res.content

    def test_reject_both_poll_id_and_poll(self, auth_client, user):
        created = svc_create_poll(owner=user, option_texts=["A", "B"])
        url = reverse("posts-list")
        res = auth_client.post(url, data={"content": "x", "poll_id": str(created.poll.id), "poll": {"options": ["C", "D"]}}, format="json")
        assert res.status_code == 400

    def test_reject_not_ready_asset(self, auth_client, user):
        a = Asset.objects.create(
            owner=user,
            type="image",
            content_type="image/png",
            size_bytes=1,
            storage_key=f"assets/test/{uuid.uuid4()}.png",
            public_url="http://x/x.png",
            status=AssetStatus.PENDING,
        )

        url = reverse("posts-list")
        res = auth_client.post(url, data={"content": "x", "asset_ids": [str(a.id)]}, format="json")
        assert res.status_code == 400
        assert b"Invalid attachments" in res.content or b"Invalid attachments detected" in res.content

    def test_reject_asset_of_other_user(self, auth_client, other_user):
        a = _mk_ready_asset(other_user)
        url = reverse("posts-list")
        res = auth_client.post(url, data={"content": "x", "asset_ids": [str(a.id)]}, format="json")
        assert res.status_code == 400

    def test_reject_asset_already_attached(self, auth_client, user):
        a = _mk_ready_asset(user)

        # 먼저 하나의 포스트를 만들어 붙임
        first = auth_client.post(reverse("posts-list"), data={"content": "a", "asset_ids": [str(a.id)]}, format="json")
        assert first.status_code == 201

        # 같은 자산으로 다시 시도 → 거절
        res = auth_client.post(reverse("posts-list"), data={"content": "b", "asset_ids": [str(a.id)]}, format="json")
        assert res.status_code == 400

    def test_reject_poll_owned_by_other(self, auth_client, other_user):
        created = svc_create_poll(owner=other_user, option_texts=["A", "B"])
        res = auth_client.post(reverse("posts-list"), data={"content": "x", "poll_id": str(created.poll.id)}, format="json")
        assert res.status_code == 400
        assert b"Invalid poll_id" in res.content

    def test_reject_reusing_same_poll_for_another_post(self, auth_client, user):
        created = svc_create_poll(owner=user, option_texts=["A", "B"])

        # 첫 포스트에서 poll 사용
        first = auth_client.post(reverse("posts-list"), data={"content": "x1", "poll_id": str(created.poll.id)}, format="json")
        assert first.status_code == 201

        # 두번째 포스트에서 같은 poll 재사용 → 거절
        second = auth_client.post(reverse("posts-list"), data={"content": "x2", "poll_id": str(created.poll.id)}, format="json")
        assert second.status_code == 400
        assert b"already attached" in second.content

    def test_requires_authentication(self):
        client = APIClient()
        res = client.post(reverse("posts-list"), data={"content": "x"}, format="json")
        assert res.status_code in (401, 403)
