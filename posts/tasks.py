import json
import logging
from typing import Any, Dict, Optional

from celery import shared_task
from django.conf import settings

log = logging.getLogger(__name__)


# ---- 간단한 이벤트 버스 발행 유틸(더미/확장 가능) ----
def publish_event(event: str, payload: Dict[str, Any], key: Optional[str] = None) -> None:
    """
    설정값 EVENT_BUS_BACKEND에 따라 이벤트를 발행한다.
    - dummy: 로그만 남김(기본값) → 테스트/로컬에서 안전
    - kafka/rabbitmq 등은 차후 veilgram.eventbus로 승격 가능
    """
    backend = getattr(settings, "EVENT_BUS_BACKEND", "dummy")
    if backend == "dummy":
        log.info("[BUS][%s] %s", event, json.dumps(payload, ensure_ascii=False))
        return

    # 아래는 확장 포인트(패키지 설치/운영 구성 후 활성화)
    if backend == "kafka":
        try:
            from confluent_kafka import Producer  # type: ignore

            producer = Producer({"bootstrap.servers": settings.KAFKA_BROKERS})
            topic = getattr(settings, "KAFKA_TOPIC_POSTS", "posts.events")
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
            exchange = getattr(settings, "RABBITMQ_EXCHANGE_POSTS", "posts.events")
            ch.exchange_declare(exchange=exchange, exchange_type="topic", durable=True)
            ch.basic_publish(exchange=exchange, routing_key=key or event, body=json.dumps({"event": event, "payload": payload}))
            conn.close()
            return
        except Exception as e:
            log.exception("RabbitMQ publish failed: %s", e)
            return

    # 미지원 백엔드: 안전하게 로그
    log.warning("Unsupported EVENT_BUS_BACKEND=%s. Fallback to log.", backend)
    log.info("[BUS][%s] %s", event, json.dumps(payload, ensure_ascii=False))


# ---- Celery 태스크: 포스트 라이프사이클 이벤트 ----
@shared_task(bind=True, name="posts.tasks.on_post_created", autoretry_for=(Exception,), retry_backoff=2, max_retries=5)
def on_post_created(self, post_id: str, author_id: str):
    # 1) 버스 발행
    publish_event("PostCreated", {"post_id": post_id, "author_id": author_id}, key="post.created")

    # 2) 알림 fan-out
    try:
        from notifications.tasks import fanout_post_created

        # 타이틀/본문은 간단히. 실제로는 다국어/포맷팅 계층을 거치는 게 좋다.
        fanout_post_created.delay(author_id=author_id, post_id=post_id, title="New post", body="A user you follow posted.")
    except Exception as e:
        log.exception("fanout_post_created dispatch failed: %s", e)

    # 3) (옵션) 피드 갱신
    try:
        from feed.tasks import on_post_created as feed_on_post_created  # type: ignore

        feed_on_post_created.delay(post_id=post_id, author_id=author_id)
    except Exception:
        # 피드 앱이 아직 없거나 비활성화된 경우를 허용
        log.debug("feed.tasks.on_post_created not wired; skipped.")

    # 4) (옵션) 검색 인덱싱
    try:
        from search.tasks import index_post  # type: ignore

        index_post.delay(post_id=post_id)
    except Exception:
        log.debug("search.tasks.index_post not wired; skipped.")


@shared_task(bind=True, name="posts.tasks.on_post_updated", autoretry_for=(Exception,), retry_backoff=2, max_retries=5)
def on_post_updated(self, post_id: str, author_id: str):
    publish_event("PostUpdated", {"post_id": post_id, "author_id": author_id}, key="post.updated")
    # 검색/피드에만 반영(알림은 보통 미발송)
    try:
        from feed.tasks import on_post_updated as feed_on_post_updated  # type: ignore

        feed_on_post_updated.delay(post_id=post_id)
    except Exception:
        log.debug("feed.tasks.on_post_updated not wired; skipped.")

    try:
        from search.tasks import update_post_index  # type: ignore

        update_post_index.delay(post_id=post_id)
    except Exception:
        log.debug("search.tasks.update_post_index not wired; skipped.")


@shared_task(bind=True, name="posts.tasks.on_post_deleted", autoretry_for=(Exception,), retry_backoff=2, max_retries=5)
def on_post_deleted(self, post_id: str, author_id: str):
    publish_event("PostDeleted", {"post_id": post_id, "author_id": author_id}, key="post.deleted")
    # 피드/검색 정리
    try:
        from feed.tasks import on_post_deleted as feed_on_post_deleted  # type: ignore

        feed_on_post_deleted.delay(post_id=post_id)
    except Exception:
        log.debug("feed.tasks.on_post_deleted not wired; skipped.")

    try:
        from search.tasks import remove_post_index  # type: ignore

        remove_post_index.delay(post_id=post_id)
    except Exception:
        log.debug("search.tasks.remove_post_index not wired; skipped.")


@shared_task(bind=True, name="posts.tasks.on_post_liked", autoretry_for=(Exception,), retry_backoff=2, max_retries=5)
def on_post_liked(self, post_id: str, actor_id: str, author_id: str):
    """
    PostLiked:
    - 버스 발행
    - 원글 작성자에게 알림(단일 사용자)
    - (옵션) 피드/검색 반영은 필요시 연결
    """
    publish_event("PostLiked", {"post_id": post_id, "actor_id": actor_id, "author_id": author_id}, key="post.liked")

    # 알림: 작성자에게 like 알림
    try:
        from notifications.tasks import single_user_push

        single_user_push.delay(user_id=author_id, type_="like", title="New like", body="Your post got a like.", data={"post_id": post_id, "by": actor_id})
    except Exception as e:
        log.exception("single_user_push for like failed: %s", e)


@shared_task(bind=True, name="posts.tasks.on_post_unliked", autoretry_for=(Exception,), retry_backoff=2, max_retries=5)
def on_post_unliked(self, post_id: str, actor_id: str, author_id: str):
    """
    PostUnliked:
    - 버스 발행만 수행(알림은 일반적으로 발송하지 않음)
    """
    publish_event("PostUnliked", {"post_id": post_id, "actor_id": actor_id, "author_id": author_id}, key="post.unliked")
    # 필요하면 카운터 재계산/정합성 보정 태스크를 연결할 수 있음


@shared_task(bind=True, name="posts.tasks.on_post_reposted", autoretry_for=(Exception,), retry_backoff=2, max_retries=5)
def on_post_reposted(self, post_id: str, actor_id: str, author_id: str, repost_id: str | None = None):
    """
    PostReposted:
    - 버스 발행
    - 원글 작성자에게 '게시물 관련' 알림(post 타입으로 매핑)
    """
    publish_event(
        "PostReposted",
        {"post_id": post_id, "actor_id": actor_id, "author_id": author_id, "repost_id": repost_id},
        key="post.reposted",
    )

    try:
        from notifications.tasks import single_user_push

        # 알림 타입은 기존 설정 키셋을 유지하기 위해 'post'로 매핑
        single_user_push.delay(
            user_id=author_id,
            type_="post",
            title="Reposted",
            body="Your post was reposted.",
            data={"post_id": post_id, "by": actor_id, "repost_id": repost_id or ""},
        )
    except Exception as e:
        log.exception("single_user_push for repost failed: %s", e)


@shared_task(bind=True, name="posts.tasks.on_post_unreposted", autoretry_for=(Exception,), retry_backoff=2, max_retries=5)
def on_post_unreposted(self, post_id: str, actor_id: str, author_id: str, repost_id: str | None = None):
    """
    PostUnreposted:
    - 버스 발행(알림은 일반적으로 발송하지 않음)
    """
    publish_event("PostUnreposted", {"post_id": post_id, "actor_id": actor_id, "author_id": author_id, "repost_id": repost_id}, key="post.unreposted")
