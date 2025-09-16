import logging
from typing import Dict

from django.db import transaction

from .models import ModerationReport
from .services import check_text

logger = logging.getLogger(__name__)


class BusConsumer:
    # 실제 환경에선 Kafka/RabbitMQ consumer가 각각의 on_* 핸들러를 호출하도록 연결.

    @classmethod
    @transaction.atomic
    def on_post_created(cls, event: Dict):
        """
        event 예시:
        {
            "type": "PostCreated",
            "payload": {"post_id": "...", "author_id": "...", "content": "..." }
        }
        """
        payload = event.get("payload", {})
        content = payload.get("content", "") or ""
        res = check_text(content)
        ModerationReport.objects.create(
            target_type="post",
            target_id=payload.get("post_id"),
            verdict=res.verdict if res.allowed else "block",
            labels=res.labels,
            score=res.score,
            matched=res.matches,
        )
        # 여기서 'block' 판정이면 추가 이벤트 발행/비공개처리(or 티켓 생성) 등으로 확장 가능
        logger.info("[Moderation] PostCreated scanned: post=%s verdict=%s score=%.2f", payload.get("post_id"), res.verdict, res.score)

    @classmethod
    @transaction.atomic
    def on_comment_created(cls, event: Dict):
        payload = event.get("payload", {})
        content = payload.get("content", "") or ""
        res = check_text(content)
        ModerationReport.objects.create(
            target_type="comment",
            target_id=payload.get("comment_id"),
            verdict=res.verdict if res.allowed else "block",
            labels=res.labels,
            score=res.score,
            matched=res.matches,
        )
        logger.info("[Moderation] CommentCreated scanned: comment=%s verdict=%s score=%.2f", payload.get("comment_id"), res.verdict, res.score)
