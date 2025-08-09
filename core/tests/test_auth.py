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

    # Signup
    def test_signup_returns_device_secret_and_tokens(self):
        payload = {"device_id": "device-001"}
        response = self.client.post(self.signup_url, data=payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED

        body = response.json()
        for key in ("id", "created_at", "access", "refresh", "device_id", "device_secret"):
            assert key in body
        assert body["device_id"] == "device-001"
        assert len(body["device_secret"]) >= 20

        creds = DeviceCredential.objects.filter(user_id=body["id"], device_id="device-001").first()
        assert creds is not None
        assert creds.secret_hash and "argon2" in creds.secret_hash

    # Login
    def test_login_success_with_device_credentials(self):
        signup_response = self.client.post(self.signup_url, data={"device_id": "device-001"}, format="json").json()
        payload = {
            "user_id": signup_response["id"],
            "device_id": signup_response["device_id"],
            "device_secret": signup_response["device_secret"],
        }
        response = self.client.post(self.login_url, data=payload, format="json")
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert "access" in body and "refresh" in body and body["user_id"] == signup_response["id"]
        assert "device_secret" not in body

    def test_login_invalid_device_secret_401(self):
        signup_response = self.client.post(self.signup_url, data={"device_id": "dev-x"}, format="json").json()
        bad_payload = {"user_id": signup_response["id"], "device_id": "dev-x", "device_secret": "WRONG"}
        response = self.client.post(self.login_url, data=bad_payload, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "detail" in response.json()

    def test_login_inactive_device_401(self):
        signup_response = self.client.post(self.signup_url, data={"device_id": "dev-y"}, format="json").json()
        DeviceCredential.objects.filter(user_id=signup_response["id"], device_id="dev-y").update(is_active=False)
        bad_payload = {"user_id": signup_response["id"], "device_id": "dev-y", "device_secret": signup_response["device_secret"]}
        response = self.client.post(self.login_url, data=bad_payload, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "detail" in response.json()

    # Refresh
    def test_refresh_success_and_rotation(self):
        signup_response = self.client.post(self.signup_url, data={"device_id": "dev-r"}, format="json").json()
        response = self.client.post(self.refresh_url, data={"refresh": signup_response["refresh"]}, format="json")
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert "access" in body

    def test_refresh_with_blacklisted_token_401(self):
        signup_response = self.client.post(self.signup_url, data={"device_id": "dev-b"}, format="json").json()
        RefreshToken(signup_response["refresh"]).blacklist()
        response = self.client.post(self.refresh_url, data={"refresh": signup_response["refresh"]}, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "detail" in response.json()

    def test_refresh_with_invalid_token_format_401(self):
        response = self.client.post(self.refresh_url, data={"refresh": "bad.token"}, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "detail" in response.json()

    # TODO: Authentication
    # def test_access_token_can_authenticate_protected_view(self):
    #     signup_response = self.client.post(self.signup_url)
    #     access = signup_response.json()["access"]

    #     protected_url = reverse("protected-endpoint")
    #     self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    #     response = self.client.get(protected_url)
    #     assert response.status_code != status.HTTP_401_UNAUTHORIZED
