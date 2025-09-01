import logging

from celery import shared_task

log = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def publish_relation_event(self, event: str, payload: dict) -> None:
    # TODO: 실제 Kafka/RabbitMQ Producer 로직 또는 Notification 호출 추가
    log.info("[CELERY] EVENT %s %s", event, payload)
