import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient

from moderation.models import ModerationRule, RuleType, ModerationReport
from moderation.services import load_rules_snapshot
from moderation.bus import BusConsumer

pytestmark = pytest.mark.django_db


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def user():
    U = get_user_model()
    return U.objects.create()


@pytest.fixture
def auth(api, user):
    api.force_authenticate(user)
    return api


@pytest.fixture(autouse=True, scope="module")
def _clear_cache_module():
    cache.clear()
    yield
    cache.clear()


class TestRulesAndCache:
    def test_create_rule_and_cache_refresh(self, auth):
        url = "/api/v1/moderation/rules/"
        payload = {"rule_type": RuleType.DENY_KEYWORD, "pattern": "spamword", "lang": "*", "severity": 2, "description": "spam keyword"}
        r = auth.post(url, data=payload, format="json")
        assert r.status_code in (201, 200)

        # 캐시에 반영되는지 확인
        snap = load_rules_snapshot(force_reload=True)
        assert "spamword" in snap["deny_keywords"]

    def test_invalidate_cache_endpoint(self, auth):
        invalidate_url = "/api/v1/moderation/rules/invalidate-cache/"
        r = auth.post(invalidate_url, data={}, format="json")
        assert r.status_code == 200


class TestCheckAPI:
    url = "/api/v1/moderation/check/"

    def test_allow(self, auth):
        ModerationRule.objects.create(rule_type=RuleType.DENY_KEYWORD, pattern="xxx", lang="*")
        # 안전한 텍스트
        r = auth.post(self.url, data={"content": "hello world"}, format="json")
        assert r.status_code == 200

        body = r.json()
        assert body["allowed"] is True
        assert body["verdict"] in ("allow", "flag")

    def test_block_by_keyword(self, auth):
        ModerationRule.objects.create(rule_type=RuleType.DENY_KEYWORD, pattern="banword", lang="*")
        # 금칙어 포함
        r = auth.post(self.url, data={"content": "this has banword inside."}, format="json")
        assert r.status_code == 200

        body = r.json()
        assert body["allowed"] is False
        assert body["verdict"] == "block"
        assert "profanity" in body["labels"]

    def test_flag_by_pattern(self, auth):
        # 전화번호 패턴과 같은 예시 정규식
        ModerationRule.objects.create(rule_type=RuleType.DENY_REGEX, pattern=r"\b\d{2,3}-\d{3,4}-\d{4}\b", lang="*")
        r = auth.post(self.url, data={"content": "연락처 010-1234-5678 주세요"}, format="json")
        assert r.status_code == 200

        body = r.json()
        assert body["allowed"] in (True, False)  # 점수 경계에 따라 flag 또는 block 가능
        assert body["verdict"] in ("flag", "block")
        assert "pattern" in body["labels"]


class TestBusConsumer:
    def test_on_post_created_generates_report(self):
        # 사전 룰
        ModerationRule.objects.create(rule_type=RuleType.DENY_KEYWORD, pattern="nasty", lang="*")
        post_id = uuid.uuid4()
        event = {"type": "PostCreated", "payload": {"post_id": str(post_id), "author_id": str(uuid.uuid4()), "content": "nasty text"}}
        BusConsumer.on_post_created(event)

        rep = ModerationReport.objects.get(target_type="post", target_id=post_id)
        assert rep.verdict in ("block", "flag")
        assert rep.score >= 0.2
        assert "profanity" in rep.labels
