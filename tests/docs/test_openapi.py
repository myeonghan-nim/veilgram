import json

import pytest
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestOpenAPISchema:
    def setup_method(self):
        self.client = APIClient()

    def test_schema_json_ok(self):
        url = reverse("schema")

        res = self.client.get(url, format="json")
        assert res.status_code == 200

        data = json.loads(res.content)

        # 핵심 필드 존재
        assert data["openapi"].startswith("3.")
        assert "paths" in data and "components" in data

        # JWT 보안스키마 노출
        assert "securitySchemes" in data["components"]
        assert "BearerAuth" in data["components"]["securitySchemes"]

    def test_docs_ui_ok(self, django_client):
        res = django_client.get(reverse("swagger-ui"))
        assert res.status_code == 200
        assert b"Swagger UI" in res.content

    def test_redoc_ui_ok(self, django_client):
        res = django_client.get(reverse("redoc"))
        assert res.status_code == 200
        assert b"ReDoc" in res.content
