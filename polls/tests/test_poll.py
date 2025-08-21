import uuid

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient


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


# ---------- Test: Poll Create ----------


class TestPollCreate:
    def test_create_ok_with_two_options(self, auth_client, user):
        url = reverse("polls-list")
        payload = {"options": ["A", "B"], "allow_multiple": False}
        res = auth_client.post(url, data=payload, format="json")
        assert res.status_code == 201

        body = res.json()
        assert body["id"]
        assert len(body["options"]) == 2
        assert body["options"][0]["position"] == 0
        assert body["options"][0]["vote_count"] == 0

    def test_reject_too_few_options(self, auth_client):
        url = reverse("polls-list")
        payload = {"options": ["OnlyOne"]}
        res = auth_client.post(url, data=payload, format="json")
        assert res.status_code == 400

    def test_reject_too_many_options(self, auth_client):
        url = reverse("polls-list")
        payload = {"options": ["1", "2", "3", "4", "5", "6"]}
        res = auth_client.post(url, data=payload, format="json")
        assert res.status_code == 400

    def test_reject_duplicate_text(self, auth_client):
        url = reverse("polls-list")
        payload = {"options": ["dup", "Dup"]}
        res = auth_client.post(url, data=payload, format="json")
        assert res.status_code == 400

    def test_requires_auth(self, anon_client):
        url = reverse("polls-list")
        res = anon_client.post(url, data={"options": ["A", "B"]}, format="json")
        assert res.status_code in (401, 403)


# ---------- Test: Vote ----------


class TestPollVote:
    def _create_poll(self, client) -> dict:
        res = client.post(reverse("polls-list"), data={"options": ["A", "B", "C"]}, format="json")
        assert res.status_code == 201
        return res.json()

    def test_vote_once_and_results(self, auth_client):
        poll = self._create_poll(auth_client)
        poll_id = poll["id"]
        opt_id = poll["options"][0]["id"]

        res = auth_client.post(reverse("polls-vote", args=[poll_id]), data={"option_id": opt_id}, format="json")
        assert res.status_code == 200

        body = res.json()
        assert body["my_option_id"] == opt_id

        # 해당 옵션 vote_count=1
        opts = {o["id"]: o for o in body["poll"]["options"]}
        assert opts[opt_id]["vote_count"] == 1

        # 결과 재조회
        res2 = auth_client.get(reverse("polls-results", args=[poll_id]))
        assert res2.status_code == 200

        opts2 = {o["id"]: o for o in res2.json()["options"]}
        assert opts2[opt_id]["vote_count"] == 1

    def test_revote_moves_between_options(self, auth_client):
        poll = self._create_poll(auth_client)
        poll_id = poll["id"]
        opt_a, opt_b = poll["options"][0]["id"], poll["options"][1]["id"]

        r1 = auth_client.post(reverse("polls-vote", args=[poll_id]), data={"option_id": opt_a}, format="json")
        assert r1.status_code == 200
        r2 = auth_client.post(reverse("polls-vote", args=[poll_id]), data={"option_id": opt_b}, format="json")
        assert r2.status_code == 200

        body = r2.json()
        opts = {o["id"]: o for o in body["poll"]["options"]}
        assert opts[opt_a]["vote_count"] == 0  # 감소
        assert opts[opt_b]["vote_count"] == 1  # 증가
        assert body["my_option_id"] == opt_b

    def test_unvote(self, auth_client):
        poll = self._create_poll(auth_client)
        poll_id = poll["id"]
        opt_id = poll["options"][0]["id"]

        auth_client.post(reverse("polls-vote", args=[poll_id]), data={"option_id": opt_id}, format="json")
        r = auth_client.post(reverse("polls-unvote", args=[poll_id]), format="json")
        assert r.status_code == 200

        body = r.json()
        opts = {o["id"]: o for o in body["poll"]["options"]}
        assert opts[opt_id]["vote_count"] == 0
        assert body["my_option_id"] is None

    def test_two_users_vote_same_option_counts_two(self, auth_client, other_client):
        poll = self._create_poll(auth_client)
        poll_id = poll["id"]
        opt_id = poll["options"][0]["id"]

        r1 = auth_client.post(reverse("polls-vote", args=[poll_id]), data={"option_id": opt_id}, format="json")
        r2 = other_client.post(reverse("polls-vote", args=[poll_id]), data={"option_id": opt_id}, format="json")
        assert r1.status_code == 200 and r2.status_code == 200

        res = auth_client.get(reverse("polls-results", args=[poll_id]))
        opts = {o["id"]: o for o in res.json()["options"]}
        assert opts[opt_id]["vote_count"] == 2

    def test_cannot_vote_with_invalid_option(self, auth_client):
        poll = self._create_poll(auth_client)
        poll_id = poll["id"]
        bad_option = uuid.uuid4()  # 다른 poll의 옵션 id라고 가정

        # PollOption 조회는 되더라도 서비스 계층에서 poll 불일치 시 ValidationError -> 400
        r = auth_client.post(reverse("polls-vote", args=[poll_id]), data={"option_id": str(bad_option)}, format="json")
        assert r.status_code == 400
