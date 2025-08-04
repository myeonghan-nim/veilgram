import uuid
from datetime import datetime

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestSignupEndpoint:
    def setup_method(self):
        self.client = APIClient()
        self.url = reverse("auth-signup")

    def test_signup_returns_expected_fields(self):
        response = self.client.post(self.url)
        assert response.status_code == status.HTTP_201_CREATED, f"Expected 201 CREATED but got {response.status_code}"

        data = response.json()
        for field in ("id", "created_at", "access", "refresh"):
            assert field in data, f"Response JSON missing '{field}'"

    def test_id_is_valid_uuid(self):
        response = self.client.post(self.url)
        data = response.json()
        returned_id = data["id"]
        parsed_id = uuid.UUID(returned_id)
        assert str(parsed_id) == returned_id

    def test_created_at_is_isoformat(self):
        response = self.client.post(self.url)
        data = response.json()
        created_at = data["created_at"]
        dt_str = created_at.rstrip("Z")
        datetime.fromisoformat(dt_str)

    def test_tokens_have_jwt_structure(self):
        response = self.client.post(self.url)
        data = response.json()
        for token_field in ("access", "refresh"):
            token = data[token_field]
            segments = token.split(".")
            assert len(segments) == 3, f"Token '{token_field}' does not have 3 segments: {token}"
