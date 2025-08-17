import uuid
from typing import Any, Dict, Optional

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from profiles.models import Profile

User = get_user_model()


@pytest.mark.django_db
class TestProfileAPI:
    BASE = "/api/v1/profiles"

    @pytest.fixture(autouse=True)
    def _setup(self, db):
        self.client = APIClient()

    def _make_user(self):
        return User.objects.create_user()

    def _auth(self, user) -> None:
        self.client.force_authenticate(user=user)

    def _json(self, res) -> Dict[str, Any]:
        try:
            return res.json()
        except Exception:
            return {}

    def _request(self, method: str, path: str, user, data: Optional[Dict[str, Any]] = None, format: str = "json", query: Optional[Dict[str, Any]] = None):
        if user is None:
            self._auth(user=None)
        else:
            self._auth(user=user)

        if query:
            from urllib.parse import urlencode

            sep = "&" if "?" in path else "?"
            path = f"{path}{sep}{urlencode(query)}"

        http = getattr(self.client, method.lower())
        return http(path, data=data, format=format)

    def _create_profile(self, user, nickname: str = "Alice", status: str = ""):
        return self._request("post", self.BASE, user=user, data={"nickname": nickname, "status_message": status})

    def _check_availability(self, user, nickname: str):
        return self._request("get", f"{self.BASE}/availability", user=user, query={"nickname": nickname})

    def test_create_profile_success(self):
        u = self._make_user()
        res = self._create_profile(u, "Alice", "hi")
        assert res.status_code == 201, res.content

        body = self._json(res)
        assert body["nickname"] == "Alice"
        assert Profile.objects.get(user=u).status_message == body["status_message"] == "hi"

    def test_create_profile_duplicate_for_same_user(self):
        u = self._make_user()
        res1 = self._create_profile(u, "Alice2")
        assert res1.status_code == 201

        res2 = self._create_profile(u, "Alice3")
        assert res2.status_code == 400
        assert "Profile already exists" in str(res2.content)

    def test_duplicate_nickname_rejected_other_user(self):
        u1, u2 = self._make_user(), self._make_user()
        assert self._create_profile(u1, "Alice").status_code == 201

        res = self._create_profile(u2, "Alice")
        assert res.status_code == 400
        assert "Already taken" in str(res.content)

    def test_forbidden_nickname_rejected(self, settings):
        settings.FORBIDDEN_NICKNAMES = ["admin", "staff"]
        u = self._make_user()
        res = self._create_profile(u, "admin")
        assert res.status_code == 400
        assert "not allowed" in str(res.content)

    def test_get_profile_by_user_id(self):
        u = self._make_user()
        assert self._create_profile(u, "Bob").status_code == 201

        res = self._request("get", f"{self.BASE}/{u.id}", user=u)
        assert res.status_code == 200
        assert self._json(res)["nickname"] == "Bob"

    def test_me_read_update_delete(self):
        u = self._make_user()
        assert self._create_profile(u, "Kate").status_code == 201

        r1 = self._request("get", f"{self.BASE}/me", user=u)
        assert r1.status_code == 200 and self._json(r1)["nickname"] == "Kate"

        r2 = self._request("patch", f"{self.BASE}/me", user=u, data={"nickname": "Kate_2"})
        assert r2.status_code == 200 and self._json(r2)["nickname"] == "Kate_2"

        r3 = self._request("delete", f"{self.BASE}/me", user=u)
        assert r3.status_code == 204
        assert not Profile.objects.filter(user=u).exists()

    def test_availability_endpoint(self, settings):
        settings.FORBIDDEN_NICKNAMES = ["root"]
        settings.FORBIDDEN_NICKNAMES_VERSION = f"testcase-{uuid.uuid4()}"

        u = self._make_user()

        assert self._create_profile(u, "Neo").status_code == 201

        ok = self._check_availability(u, "Trinity")
        assert ok.status_code == 200 and self._json(ok)["available"] is True

        no = self._check_availability(u, "root")
        no_body = self._json(no)
        assert no.status_code == 200 and no_body["available"] is False
        assert any("Forbidden" in r for r in no_body["reasons"])

        dupe = self._check_availability(u, "neo")
        dupe_body = self._json(dupe)
        assert dupe.status_code == 200 and dupe_body["available"] is False
        assert any("Duplicate" in r for r in dupe_body["reasons"])
