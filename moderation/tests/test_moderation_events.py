import uuid

import pytest
from django.utils import timezone

from moderation.bus import BusConsumer
from moderation.models import ModerationReport, ModerationRule, RuleType
from moderation.services import invalidate_rules_cache, upsert_rule

pytestmark = pytest.mark.django_db


class BaseModerationEventTest:
    @pytest.fixture(autouse=True)
    def _clean_rules_cache(self):
        # 룰/캐시 초기화
        ModerationRule.objects.all().delete()
        invalidate_rules_cache()


class TestPostCreated(BaseModerationEventTest):
    def test_block_on_banned_keyword(self):
        # 금칙어 룰 추가 → 키워드 1개면 score = 0.3 + 0.2(NSFW휴리스틱) = 0.5 → block
        upsert_rule(RuleType.DENY_KEYWORD, "spam", severity=2, description="ban spam")

        post_id = str(uuid.uuid4())
        evt = {
            "type": "PostCreated",
            "payload": {
                "post_id": post_id,
                "author_id": str(uuid.uuid4()),
                "content": "This post contains SPAM content.",
                "created_ms": int(timezone.now().timestamp() * 1000),
            },
        }

        BusConsumer.on_post_created(evt)

        rep = ModerationReport.objects.get(target_type="post", target_id=post_id)
        assert rep.verdict == "block"
        assert "profanity" in rep.labels
        # 어떤 패턴이 맞았는지 기록되었는지
        assert any(m["pattern"].lower() == "spam" for m in rep.matched)

    def test_flag_on_regex_match_only(self):
        # 정규식 1회 매치 → score = 0.4 → flag (allow=True)
        upsert_rule(RuleType.DENY_REGEX, r"danger(ous)?", severity=1, description="soft regex")

        post_id = str(uuid.uuid4())
        evt = {
            "type": "PostCreated",
            "payload": {
                "post_id": post_id,
                "author_id": str(uuid.uuid4()),
                "content": "This looks dangerous but not explicitly banned.",
                "created_ms": int(timezone.now().timestamp() * 1000),
            },
        }

        BusConsumer.on_post_created(evt)

        rep = ModerationReport.objects.get(target_type="post", target_id=post_id)
        assert rep.verdict == "flag"
        assert "pattern" in rep.labels
        assert any(m["type"] == "regex" for m in rep.matched)

    def test_allow_when_no_rules_match(self):
        post_id = str(uuid.uuid4())
        evt = {
            "type": "PostCreated",
            "payload": {
                "post_id": post_id,
                "author_id": str(uuid.uuid4()),
                "content": "hello world, nice day!",
                "created_ms": int(timezone.now().timestamp() * 1000),
            },
        }

        BusConsumer.on_post_created(evt)

        rep = ModerationReport.objects.get(target_type="post", target_id=post_id)
        assert rep.verdict == "allow"
        assert rep.score < 0.2
        assert rep.labels == []


class TestCommentCreated(BaseModerationEventTest):
    def test_block_comment_on_banned_keyword(self):
        upsert_rule(RuleType.DENY_KEYWORD, "abuse", severity=3, description="ban abuse")

        comment_id = str(uuid.uuid4())
        evt = {
            "type": "CommentCreated",
            "payload": {
                "comment_id": comment_id,
                "author_id": str(uuid.uuid4()),
                "content": "This contains abuse terms.",
                "created_ms": int(timezone.now().timestamp() * 1000),
            },
        }

        BusConsumer.on_comment_created(evt)

        rep = ModerationReport.objects.get(target_type="comment", target_id=comment_id)
        assert rep.verdict == "block"
        assert "profanity" in rep.labels
        assert rep.score >= 0.5
