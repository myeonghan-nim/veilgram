import uuid

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from relations.models import Follow

User = get_user_model()


@pytest.mark.django_db
class TestRelationsAPI:
    PROFILES_BASE = "/api/v1/profiles"
    USERS_BASE = "/api/v1/users"

    @pytest.fixture(autouse=True)
    def _setup(self, db):
        self.client = APIClient()

    @pytest.fixture(autouse=True)
    def _forbidden_cache_version(self, settings):
        settings.FORBIDDEN_NICKNAMES_VERSION = f"test-{uuid.uuid4()}"

    def _make_user(self):
        return User.objects.create_user()

    def _request(self, method, path, user=None, data=None, format="json"):
        self.client.force_authenticate(user=user)
        return getattr(self.client, method.lower())(path, data=data, format=format)

    def _create_profile(self, user, nickname):
        return self._request("post", self.PROFILES_BASE, user=user, data={"nickname": nickname, "status_message": ""})

    def _json(self, res):
        try:
            return res.json()
        except Exception:
            return {}

    def _follow_url(self, target_id):
        return f"{self.USERS_BASE}/{target_id}/follow"

    def _block_url(self, target_id):
        return f"{self.USERS_BASE}/{target_id}/block"

    # ---- follow / unfollow ----
    def test_follow_success_updates_counts_and_flags(self):
        a, b = self._make_user(), self._make_user()
        assert self._create_profile(a, "AA").status_code == 201
        assert self._create_profile(b, "BB").status_code == 201

        res = self._request("post", self._follow_url(b.id), user=a)
        assert res.status_code == 204

        prof = self._request("get", f"{self.PROFILES_BASE}/{b.id}", user=a)
        body = self._json(prof)
        assert prof.status_code == 200
        assert body["follower_count"] == 1
        assert body["following_count"] == 0
        assert body["relations"]["is_following"] is True
        assert body["relations"]["is_followed_by"] is False

    def test_follow_duplicate_returns_400(self):
        a, b = self._make_user(), self._make_user()
        assert self._create_profile(a, "AA").status_code == 201
        assert self._create_profile(b, "BB").status_code == 201

        assert self._request("post", self._follow_url(b.id), user=a).status_code == 204
        dup = self._request("post", self._follow_url(b.id), user=a)
        assert dup.status_code == 400
        assert "Already following" in str(dup.content)

    def test_unfollow_success_and_not_following_400(self):
        a, b = self._make_user(), self._make_user()
        assert self._create_profile(a, "AA").status_code == 201
        assert self._create_profile(b, "BB").status_code == 201

        assert self._request("post", self._follow_url(b.id), user=a).status_code == 204

        res = self._request("delete", self._follow_url(b.id), user=a)
        assert res.status_code == 204
        assert not Follow.objects.filter(follower=a, following=b).exists()

        res2 = self._request("delete", self._follow_url(b.id), user=a)
        assert res2.status_code == 400
        assert "Not following" in str(res2.content)

    def test_cannot_follow_self(self):
        a = self._make_user()
        assert self._create_profile(a, "AA").status_code == 201
        res = self._request("post", self._follow_url(a.id), user=a)
        assert res.status_code == 400
        assert "Cannot target yourself" in str(res.content)

    # ---- block / unblock ----
    def test_block_auto_unfollow_both_directions(self):
        a, b = self._make_user(), self._make_user()
        assert self._create_profile(a, "AA").status_code == 201
        assert self._create_profile(b, "BB").status_code == 201

        # 상호 팔로우
        assert self._request("post", self._follow_url(b.id), user=a).status_code == 204
        assert self._request("post", self._follow_url(a.id), user=b).status_code == 204

        # A가 B 차단 → 양방향 언팔
        assert self._request("post", self._block_url(b.id), user=a).status_code == 204
        assert not Follow.objects.filter(follower=a, following=b).exists()
        assert not Follow.objects.filter(follower=b, following=a).exists()

    def test_block_prevents_follow_both_ways_and_unblock_then_follow(self):
        a, b = self._make_user(), self._make_user()
        assert self._create_profile(a, "AA").status_code == 201
        assert self._create_profile(b, "BB").status_code == 201

        # 차단 중엔 서로 팔로우 불가
        assert self._request("post", self._block_url(b.id), user=a).status_code == 204
        r1 = self._request("post", self._follow_url(b.id), user=a)
        r2 = self._request("post", self._follow_url(a.id), user=b)
        assert r1.status_code in (403, 400)
        assert r2.status_code in (403, 400)

        # 언블록 후 팔로우 가능
        assert self._request("delete", self._block_url(b.id), user=a).status_code == 204
        ok = self._request("post", self._follow_url(b.id), user=a)
        assert ok.status_code == 204

    def test_block_duplicate_and_unblock_not_blocked(self):
        a, b = self._make_user(), self._make_user()
        assert self._create_profile(a, "AA").status_code == 201
        assert self._create_profile(b, "BB").status_code == 201

        assert self._request("post", self._block_url(b.id), user=a).status_code == 204
        dup = self._request("post", self._block_url(b.id), user=a)
        assert dup.status_code == 400
        assert "Already blocked" in str(dup.content)

        not_blocked = self._request("delete", self._block_url(a.id), user=b)
        assert not_blocked.status_code == 400
        assert "Not blocked" in str(not_blocked.content)

    def test_cannot_block_self(self):
        a = self._make_user()
        assert self._create_profile(a, "AA").status_code == 201
        res = self._request("post", self._block_url(a.id), user=a)
        assert res.status_code == 400
        assert "Cannot target yourself" in str(res.content)
