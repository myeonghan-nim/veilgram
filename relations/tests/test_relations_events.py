import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from relations import events as rel_events

User = get_user_model()


@pytest.mark.django_db
class TestRelationEvents:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.client = APIClient()

    def _make_user(self):
        return User.objects.create_user()

    def _profiles_base(self):
        return "/api/v1/profiles"

    def _users_base(self):
        return "/api/v1/users"

    def _follow_url(self, tid):
        return f"{self._users_base()}/{tid}/follow"

    def _block_url(self, tid):
        return f"{self._users_base()}/{tid}/block"

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def test_follow_emits_event(self, monkeypatch):
        a, b = self._make_user(), self._make_user()
        self._auth(a)
        self.client.post(self._profiles_base(), {"nickname": "AA", "status_message": ""}, format="json")
        self.client.post(self._profiles_base(), {"nickname": "BB", "status_message": ""}, format="json")

        recorded = []
        monkeypatch.setattr(rel_events, "emit", lambda e, p: recorded.append((e, p)))
        assert self.client.post(self._follow_url(b.id), format="json").status_code == 204
        assert ("UserFollowed", {"follower_id": str(a.id), "following_id": str(b.id)}) in recorded

    def test_unfollow_emits_event(self, monkeypatch):
        a, b = self._make_user(), self._make_user()
        self._auth(a)
        self.client.post(self._profiles_base(), {"nickname": "AA", "status_message": ""}, format="json")
        self.client.post(self._profiles_base(), {"nickname": "BB", "status_message": ""}, format="json")

        self.client.post(self._follow_url(b.id), format="json")
        recorded = []
        monkeypatch.setattr(rel_events, "emit", lambda e, p: recorded.append((e, p)))
        assert self.client.delete(self._follow_url(b.id)).status_code == 204
        assert ("UserUnfollowed", {"follower_id": str(a.id), "following_id": str(b.id)}) in recorded

    def test_block_emits_block_and_unfollow_events(self, monkeypatch):
        a, b = self._make_user(), self._make_user()
        self._auth(a)
        self.client.post(self._profiles_base(), {"nickname": "AA", "status_message": ""}, format="json")
        self.client.post(self._profiles_base(), {"nickname": "BB", "status_message": ""}, format="json")

        # 상호 팔로우
        self.client.post(self._follow_url(b.id), format="json")
        self._auth(b)
        self.client.post(self._follow_url(a.id), format="json")
        self._auth(a)

        recorded = []
        monkeypatch.setattr(rel_events, "emit", lambda e, p: recorded.append((e, p)))
        assert self.client.post(self._block_url(b.id), format="json").status_code == 204
        assert ("UserBlocked", {"user_id": str(a.id), "blocked_user_id": str(b.id)}) in recorded

        # 양방향 언팔 이벤트가 최소 2건(관계 수만큼) 포함
        unfollows = [x for x in recorded if x[0] == "UserUnfollowed"]
        assert len(unfollows) >= 2
