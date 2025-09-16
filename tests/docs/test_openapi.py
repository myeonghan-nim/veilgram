import json

import pytest
import yaml
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestOpenAPISchema:
    def setup_method(self):
        self.client = APIClient()

    def _load_schema(self, response):
        ct = (response.headers.get("Content-Type") or "").lower()
        body = response.content
        if "json" in ct or (body[:1] in (b"{", b"[")):
            return json.loads(body)
        return yaml.safe_load(body)

    def test_schema_json_ok(self):
        res = self.client.get(reverse("schema"))
        assert res.status_code == 200
        data = self._load_schema(res)
        assert str(data.get("openapi", "")).startswith("3.")
        assert "paths" in data and "components" in data
        schemes = (data.get("components") or {}).get("securitySchemes") or {}
        assert any(name in schemes for name in ("BearerAuth", "jwtAuth", "TokenAuth")), f"securitySchemes keys: {list(schemes.keys())}"

    def test_docs_ui_ok(self):
        res = self.client.get(reverse("swagger-ui"))
        assert res.status_code == 200
        body = res.content
        # Swagger UI 템플릿의 안정적인 시그니처를 검사
        assert any(
            marker in body
            for marker in (
                b"SwaggerUIBundle",  # 핵심 초기화 스크립트
                b"swagger-ui.css",  # CSS 링크
                b"swagger-ui-standalone-preset",  # 프리셋 스크립트
            )
        ), body[
            :2000
        ]  # 실패시 본문 일부를 보여주도록

    def test_redoc_ui_ok(self):
        res = self.client.get(reverse("redoc"))
        assert res.status_code == 200
        body = res.content
        # ReDoc도 문자열 표기가 다를 수 있어 스크립트 파일명을 기준으로 검사
        assert any(
            marker in body
            for marker in (
                b"redoc.standalone.js",
                b"Redoc",  # 일부 템플릿에서 Title/텍스트로 등장
                b"ReDoc",  # 대소문자 변형 대비
            )
        ), body[:2000]
