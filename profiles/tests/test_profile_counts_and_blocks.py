import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from relations.models import Follow, Block

User = get_user_model()


@pytest.mark.django_db
class TestProfileAPICountsAndBlocks:
    BASE = "/api/v1/profiles"

    @pytest.fixture(autouse=True)
    def _setup(self, db):
        self.client = APIClient()

    def _make_user(self):
        return User.objects.create_user()

    def _request(self, method, path, user=None, data=None, format="json", query=None):
        if user is None:
            self.client.force_authenticate(user=None)
        else:
            self.client.force_authenticate(user=user)

        http = getattr(self.client, method.lower())
        if query:
            from urllib.parse import urlencode

            path = f"{path}?{urlencode(query)}"
        return http(path, data=data, format=format)

    def _create_profile(self, user, nickname, status=""):
        return self._request("post", self.BASE, user=user, data={"nickname": nickname, "status_message": status})

    def _follow(self, follower, following):
        return Follow.objects.create(follower=follower, following=following)

    def _block(self, user, target):
        return Block.objects.create(user=user, blocked_user=target)

    def _json(self, res):
        try:
            return res.json()
        except Exception:
            return {}

    def test_profile_counts_basic(self):
        user_a, user_b, user_c = self._make_user(), self._make_user(), self._make_user()
        assert self._create_profile(user_a, "AA").status_code == 201
        assert self._create_profile(user_b, "BB").status_code == 201
        assert self._create_profile(user_c, "CC").status_code == 201

        # make some follows
        self._follow(user_b, user_a)  # B -> A (A's followers +1)
        self._follow(user_c, user_a)  # C -> A (A's followers +1)
        self._follow(user_a, user_b)  # A -> B (A's following +1, B's followers +1)

        # Check A's profile
        res = self._request("get", f"{self.BASE}/{user_a.id}")
        body = self._json(res)
        assert res.status_code == 200
        assert body["follower_count"] == 2
        assert body["following_count"] == 1

        # Check B's profile from A's perspective
        res2 = self._request("get", f"{self.BASE}/{user_b.id}", user=user_a)
        b2 = self._json(res2)
        assert res2.status_code == 200
        assert b2["follower_count"] == 1
        assert b2["following_count"] == 1

        # relations flags
        assert b2["relations"]["is_following"] is True  # From A viewing B's profile: Is A following B? (True)
        assert b2["relations"]["is_followed_by"] is True  # Is B following A? (True)
        # Note about perspective:
        # - is_following: "Is the requester (request.user) following the target (user_id)?"
        # - is_followed_by: "Is the target following the requester?"

    def test_profile_relations_flags_block(self):
        user_a, user_b = self._make_user(), self._make_user()
        assert self._create_profile(user_a, "AA").status_code == 201
        assert self._create_profile(user_b, "BB").status_code == 201

        self._block(user_a, user_b)  # A blocks B

        # Check B`s profile from A
        r1 = self._request("get", f"{self.BASE}/{user_b.id}", user=user_a)
        b1 = self._json(r1)
        assert r1.status_code == 200
        assert b1["relations"]["is_blocked_by_me"] is True
        assert b1["relations"]["has_blocked_me"] is False

        # Check A's profile from B
        r2 = self._request("get", f"{self.BASE}/{user_a.id}", user=user_b)
        b2 = self._json(r2)
        assert r2.status_code == 200
        assert b2["relations"]["is_blocked_by_me"] is False
        assert b2["relations"]["has_blocked_me"] is True

    def test_profile_counts_not_affected_by_block(self):
        user_a, user_b = self._make_user(), self._make_user()
        assert self._create_profile(user_a, "AA").status_code == 201
        assert self._create_profile(user_b, "BB").status_code == 201

        self._follow(user_b, user_a)  # B -> A
        self._block(user_a, user_b)  # A blocks B

        res = self._request("get", f"{self.BASE}/{user_a.id}", user=user_b)
        body = self._json(res)
        assert res.status_code == 200
        assert body["follower_count"] == 1  # B is still following A
