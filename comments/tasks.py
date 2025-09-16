import json
import logging
from typing import Any, Dict, Optional, Set

from celery import shared_task
from django.conf import settings

log = logging.getLogger(__name__)


# ---- 간이 이벤트 버스 유틸 (posts.tasks와 동일 패턴; 이후 core.eventbus로 승격 권장) ----
def publish_event(event: str, payload: Dict[str, Any], key: Optional[str] = None) -> None:
    backend = getattr(settings, "EVENT_BUS_BACKEND", "dummy")
    if backend == "dummy":
        log.info("[BUS][%s] %s", event, json.dumps(payload, ensure_ascii=False))
        return

    if backend == "kafka":
        try:
            from confluent_kafka import Producer  # type: ignore

            producer = Producer({"bootstrap.servers": settings.KAFKA_BROKERS})
            topic = getattr(settings, "KAFKA_TOPIC_COMMENTS", "comments.events")
            producer.produce(topic, key=key or event, value=json.dumps({"event": event, "payload": payload}))
            producer.flush(5)
            return
        except Exception as e:
            log.exception("Kafka publish failed: %s", e)
            return

    if backend == "rabbitmq":
        try:
            import pika  # type: ignore

            params = pika.URLParameters(settings.RABBITMQ_URL)
            conn = pika.BlockingConnection(params)
            ch = conn.channel()
            exchange = getattr(settings, "RABBITMQ_EXCHANGE_COMMENTS", "comments.events")
            ch.exchange_declare(exchange=exchange, exchange_type="topic", durable=True)
            ch.basic_publish(exchange=exchange, routing_key=key or event, body=json.dumps({"event": event, "payload": payload}))
            conn.close()
            return
        except Exception as e:
            log.exception("RabbitMQ publish failed: %s", e)
            return

    log.warning("Unsupported EVENT_BUS_BACKEND=%s. Fallback to log.", backend)
    log.info("[BUS][%s] %s", event, json.dumps(payload, ensure_ascii=False))


# ---- Celery 태스크 ----
@shared_task(bind=True, name="comments.tasks.on_comment_created", autoretry_for=(Exception,), retry_backoff=2, max_retries=5)
def on_comment_created(self, comment_id: str, post_id: str, author_id: str, parent_id: str = "", post_author_id: str = "", parent_author_id: str = ""):
    # --- 이벤트 버스 발행 ---
    publish_event(
        "CommentCreated",
        {
            "comment_id": comment_id,
            "post_id": post_id,
            "author_id": author_id,
            "parent_id": parent_id,
        },
        key="comment.created",
    )

    # --- 알림 수신자 결정 ---
    recipients: Set[str] = set()
    if post_author_id and post_author_id != author_id:
        recipients.add(post_author_id)
    if parent_author_id and parent_author_id not in (author_id, post_author_id):
        recipients.add(parent_author_id)

    if not recipients:
        return 0

    # --- 알림 전송 (인앱 + 푸시) ---
    try:
        from notifications.tasks import single_user_push
    except Exception as e:
        log.exception("notifications integration missing: %s", e)
        return 0

    sent_total = 0
    for uid in recipients:
        try:
            sent = single_user_push.delay(
                user_id=uid,
                type_="comment",
                title="New comment",
                body="There is a new comment.",
                data={
                    "post_id": post_id,
                    "comment_id": comment_id,
                    "by": author_id,
                    "parent_id": parent_id,
                },
            )
            # ALWAYS_EAGER이면 숫자, 비동기면 AsyncResult라 합산은 생략 가능
            sent_total += int(getattr(sent, "result", 0)) if hasattr(sent, "result") else 0
        except Exception as e:
            log.exception("single_user_push failed for uid=%s: %s", uid, e)
    return sent_total


@shared_task(bind=True, name="comments.tasks.on_comment_updated", autoretry_for=(Exception,), retry_backoff=2, max_retries=5)
def on_comment_updated(self, comment_id: str, post_id: str, author_id: str):
    publish_event(
        "CommentUpdated",
        {
            "comment_id": comment_id,
            "post_id": post_id,
            "author_id": author_id,
        },
        key="comment.updated",
    )
    # 보통 업데이트는 알림 미발송. 필요시 검색/모더레이션 재평가 태스크 연결.


@shared_task(bind=True, name="comments.tasks.on_comment_deleted", autoretry_for=(Exception,), retry_backoff=2, max_retries=5)
def on_comment_deleted(self, comment_id: str, post_id: str, author_id: str):
    publish_event(
        "CommentDeleted",
        {
            "comment_id": comment_id,
            "post_id": post_id,
            "author_id": author_id,
        },
        key="comment.deleted",
    )
    # 필요시 카운터 보정/피드 정리/검색 인덱스 제거 등 연계
