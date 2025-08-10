import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import DeviceCredential


@pytest.mark.django_db
class TestAuthEndpoints:
    def setup_method(self):
        self.client = APIClient()
        self.signup_url = reverse("auth-signup")
        self.login_url = reverse("auth-login")
        self.refresh_url = reverse("auth-refresh")

    def _signup_user(self, device_id):
        return self.client.post(self.signup_url, data={"device_id": device_id}, format="json")

    def _login_user(self, user_id, device_id, device_secret):
        return self.client.post(self.login_url, data={"user_id": user_id, "device_id": device_id, "device_secret": device_secret}, format="json")

    # Signup
    def test_signup_returns_device_secret_and_tokens(self):
        res = self._signup_user(device_id="device-001")
        assert res.status_code == status.HTTP_201_CREATED

        body = res.json()
        for key in ("id", "created_at", "access", "refresh", "device_id", "device_secret"):
            assert key in body
        assert body["device_id"] == "device-001"
        assert len(body["device_secret"]) >= 20

        creds = DeviceCredential.objects.filter(user_id=body["id"], device_id=body["device_id"]).first()
        assert creds is not None
        assert creds.secret_hash and "argon2" in creds.secret_hash

    # Login
    def test_login_success_with_device_credentials(self):
        s = self._signup_user(device_id="device-001").json()
        res = self._login_user(user_id=s["id"], device_id=s["device_id"], device_secret=s["device_secret"])
        assert res.status_code == status.HTTP_200_OK

        body = res.json()
        assert "access" in body and "refresh" in body and body["user_id"] == s["id"]
        assert "device_secret" not in body

    def test_login_invalid_device_secret_401(self):
        s = self._signup_user(device_id="dev-x").json()
        res = self._login_user(user_id=s["id"], device_id=s["device_id"], device_secret="WRONG")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert "detail" in res.json()

    def test_login_inactive_device_401(self):
        s = self._signup_user(device_id="dev-y").json()
        DeviceCredential.objects.filter(user_id=s["id"], device_id=s["device_id"]).update(is_active=False)

        res = self.client.post(self.login_url, data={"user_id": s["id"], "device_id": s["device_id"], "device_secret": s["device_secret"]}, format="json")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert "detail" in res.json()

    # Refresh
    def test_refresh_success_and_rotation(self):
        s = self._signup_user(device_id="dev-r").json()
        res = self.client.post(self.refresh_url, data={"refresh": s["refresh"]}, format="json")
        assert res.status_code == status.HTTP_200_OK

        body = res.json()
        assert "access" in body

    def test_refresh_with_blacklisted_token_401(self):
        s = self._signup_user(device_id="dev-b").json()
        RefreshToken(s["refresh"]).blacklist()

        res = self.client.post(self.refresh_url, data={"refresh": s["refresh"]}, format="json")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert "detail" in res.json()

    def test_refresh_with_invalid_token_format_401(self):
        res = self.client.post(self.refresh_url, data={"refresh": "bad.token"}, format="json")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert "detail" in res.json()

    # TODO: Authentication
    # def test_access_token_can_authenticate_protected_view(self):
    #     signup_response = self.client.post(self.signup_url)
    #     access = signup_response.json()["access"]

    #     protected_url = reverse("protected-endpoint")
    #     self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    #     response = self.client.get(protected_url)
    #     assert response.status_code != status.HTTP_401_UNAUTHORIZED
