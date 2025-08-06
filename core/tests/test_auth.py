import uuid
from datetime import datetime

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken


@pytest.mark.django_db
class TestAuthEndpoints:
    def setup_method(self):
        self.client = APIClient()
        self.signup_url = reverse("auth-signup")
        self.login_url = reverse("auth-login")
        self.refresh_url = reverse("auth-refresh")

    # Signup
    def test_signup_returns_expected_fields(self):
        response = self.client.post(self.signup_url)
        assert response.status_code == status.HTTP_201_CREATED, f"Expected 201 CREATED but got {response.status_code}"

        data = response.json()
        for field in ("id", "created_at", "access", "refresh"):
            assert field in data, f"Response JSON missing '{field}'"

    def test_id_is_valid_uuid(self):
        response = self.client.post(self.signup_url)
        data = response.json()
        returned_id = data["id"]
        parsed_id = uuid.UUID(returned_id)
        assert str(parsed_id) == returned_id, f"Returned ID '{returned_id}' is not a valid UUID"

    def test_created_at_is_isoformat(self):
        response = self.client.post(self.signup_url)
        data = response.json()
        created_at = data["created_at"]
        dt_str = created_at.rstrip("Z")
        datetime.fromisoformat(dt_str), f"Created at '{created_at}' is not in ISO format"

    def test_tokens_have_jwt_structure(self):
        response = self.client.post(self.signup_url)
        data = response.json()
        for token_field in ("access", "refresh"):
            token = data[token_field]
            segments = token.split(".")
            assert len(segments) == 3, f"Token '{token_field}' does not have 3 segments: {token}"

    # Login
    def test_login_with_valid_refresh_issues_tokens(self):
        signup_response = self.client.post(self.signup_url)
        assert signup_response.status_code == status.HTTP_201_CREATED, "Signup did not return 201 CREATED"
        refresh_token = signup_response.json()["refresh"]

        response = self.client.post(self.login_url, data={"refresh": refresh_token})
        assert response.status_code == status.HTTP_200_OK, f"Expected 200 OK but got {response.status_code}"

        data = response.json()
        assert "access" in data, "Response JSON missing 'access' token"
        assert "refresh" in data, "Response JSON missing 'refresh' token"

    def test_login_requires_refresh_token(self):
        response = self.client.post(self.login_url, data={})
        assert response.status_code == status.HTTP_400_BAD_REQUEST, "Login without refresh token should return 400 BAD REQUEST"

    def test_login_with_blacklisted_refresh_token(self):
        signup_response = self.client.post(self.signup_url)
        assert signup_response.status_code == status.HTTP_201_CREATED, "Signup did not return 201 CREATED"

        blacklisted = signup_response.json()["refresh"]
        RefreshToken(blacklisted).blacklist()

        response = self.client.post(self.login_url, {"refresh": blacklisted})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, f"Expected 401 UNAUTHORIZED but got {response.status_code}"
        assert "detail" in response.json(), "Response JSON missing 'detail' field"

    def test_login_with_invalid_token_format(self):
        response = self.client.post(self.login_url, {"refresh": "not.a.valid.token"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, f"Expected 401 UNAUTHORIZED but got {response.status_code}"
        body = response.json()
        assert "detail" in body, "Response JSON missing 'detail' field"

    # Refresh
    def test_refresh_endpoint_issues_new_access(self):
        signup_response = self.client.post(self.signup_url)
        original_refresh = signup_response.json()["refresh"]

        response = self.client.post(self.refresh_url, data={"refresh": original_refresh})
        assert response.status_code == status.HTTP_200_OK, f"Expected 200 OK but got {response.status_code}"

        data = response.json()
        assert "access" in data, "Response JSON missing 'access' token"
        assert "refresh" in data, "Response JSON missing 'refresh' token"

    def test_refresh_with_blacklisted_refresh_token(self):
        signup_response = self.client.post(self.signup_url)
        assert signup_response.status_code == status.HTTP_201_CREATED, "Signup did not return 201 CREATED"

        original = signup_response.json()["refresh"]
        RefreshToken(original).blacklist()

        response = self.client.post(self.refresh_url, {"refresh": original})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, f"Expected 401 UNAUTHORIZED but got {response.status_code}"
        assert "detail" in response.json(), "Response JSON missing 'detail' field"

    def test_refresh_with_invalid_token_format(self):
        response = self.client.post(self.refresh_url, {"refresh": "bad.token"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, f"Expected 401 UNAUTHORIZED but got {response.status_code}"
        body = response.json()
        assert "detail" in body, "Response JSON missing 'detail' field"

    # TODO: Authentication
    # def test_access_token_can_authenticate_protected_view(self):
    #     signup_response = self.client.post(self.signup_url)
    #     access = signup_response.json()["access"]

    #     protected_url = reverse("protected-endpoint")
    #     self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    #     response = self.client.get(protected_url)
    #     assert response.status_code != status.HTTP_401_UNAUTHORIZED
