import logging
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from feed.event_consumer_runtime import handle_message

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Feed event consumer (Kafka/RabbitMQ) using FEED_* settings and event_dispather.dispatch"

    def handle(self, *args, **options):
        driver = getattr(settings, "FEED_BUS_DRIVER", "kafka")
        if driver == "kafka":
            return self._run_kafka()
        elif driver == "rabbitmq":
            return self._run_rabbit()
        self.stderr.write(self.style.ERROR(f"Unsupported FEED_BUS_DRIVER={driver}"))
        return 2

    # ---------- Kafka ----------
    def _run_kafka(self):
        from confluent_kafka import Consumer  # type: ignore

        conf = {
            "bootstrap.servers": settings.FEED_KAFKA_BOOTSTRAP,
            "group.id": settings.FEED_KAFKA_GROUP_ID,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,  # 처리 실패 시에도 손실 없는 파이프를 원하면 수동 커밋 설계 권장
        }
        topics = list(getattr(settings, "FEED_KAFKA_TOPICS", []))
        self.stdout.write(self.style.SUCCESS(f"[FeedConsumer] Kafka subscribe {topics} @ {conf['bootstrap.servers']} (group={conf['group.id']})"))

        c = Consumer(conf)
        c.subscribe(topics)
        try:
            while True:
                msg = c.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    log.error("Kafka error: %s", msg.error())
                    continue
                try:
                    handle_message(msg.value())
                except Exception as e:
                    log.exception("Kafka message handling failed: %s", e)
                    # 필요 시 dead-letter 토픽 설계 권장
        except KeyboardInterrupt:
            pass
        finally:
            c.close()

    # ---------- RabbitMQ ----------
    def _run_rabbit(self):
        import pika  # type: ignore

        url = settings.FEED_RABBIT_URL
        exchange = settings.FEED_RABBIT_EXCHANGE
        queue = settings.FEED_RABBIT_QUEUE
        bindings = list(getattr(settings, "FEED_RABBIT_BINDINGS", []))

        self.stdout.write(self.style.SUCCESS(f"[FeedConsumer] Rabbit {url} exchange={exchange} queue={queue} bind={bindings}"))

        params = pika.URLParameters(url)
        while True:
            try:
                conn = pika.BlockingConnection(params)
                ch = conn.channel()
                ch.exchange_declare(exchange=exchange, exchange_type="topic", durable=True)
                ch.queue_declare(queue=queue, durable=True)
                for rk in bindings:
                    ch.queue_bind(exchange=exchange, queue=queue, routing_key=rk)

                def on_message(ch_, method, properties, body):
                    try:
                        handle_message(body)
                        ch_.basic_ack(delivery_tag=method.delivery_tag)
                    except Exception:
                        # 재처리 전략이 없다면 재큐잉보다는 DLQ로 흘리도록 nack(requeue=False)
                        ch_.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

                ch.basic_qos(prefetch_count=100)
                ch.basic_consume(queue=queue, on_message_callback=on_message)
                ch.start_consuming()
            except pika.exceptions.AMQPConnectionError as e:
                log.error("Rabbit connection lost: %s. Reconnecting in 3s...", e)
                time.sleep(3)
                continue
