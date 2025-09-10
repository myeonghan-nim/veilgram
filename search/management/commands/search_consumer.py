from __future__ import annotations
import time
import logging

from django.conf import settings
from django.core.management.base import BaseCommand

from search.event_consumer_runtime import handle_message

log = logging.getLogger(__name__)


def _bus_driver():
    # 검색 전용 설정이 없으면 피드 설정을 재사용
    return getattr(settings, "SEARCH_BUS_DRIVER", getattr(settings, "FEED_BUS_DRIVER", "kafka"))


def _topics():
    return list(getattr(settings, "SEARCH_EVENT_TOPICS", getattr(settings, "FEED_EVENT_TOPICS", ["post.events", "hashtag.events", "user.events"])))


class Command(BaseCommand):
    help = "Search event consumer (Kafka/RabbitMQ)"

    def handle(self, *args, **opts):
        driver = _bus_driver()
        if driver == "kafka":
            return self._run_kafka()
        elif driver == "rabbitmq":
            return self._run_rabbit()
        self.stderr.write(self.style.ERROR(f"Unsupported bus driver: {driver}"))
        return 2

    # Kafka
    def _run_kafka(self):
        from confluent_kafka import Consumer  # type: ignore

        conf = {
            "bootstrap.servers": getattr(settings, "FEED_KAFKA_BOOTSTRAP", "kafka:9092"),
            "group.id": getattr(settings, "SEARCH_KAFKA_GROUP_ID", "search-service"),
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,
        }
        topics = _topics()
        self.stdout.write(self.style.SUCCESS(f"[SearchConsumer] Kafka {topics} @ {conf['bootstrap.servers']} (group={conf['group.id']})"))

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
                except Exception:
                    log.exception("handle_message failed")
        except KeyboardInterrupt:
            pass
        finally:
            c.close()

    # RabbitMQ
    def _run_rabbit(self):
        import pika  # type: ignore

        url = getattr(settings, "FEED_RABBIT_URL", "amqp://guest:guest@rabbitmq:5672/")
        exchange = getattr(settings, "FEED_RABBIT_EXCHANGE", "app.events")
        queue = getattr(settings, "SEARCH_RABBIT_QUEUE", "search.service")
        bindings = _topics()

        self.stdout.write(self.style.SUCCESS(f"[SearchConsumer] Rabbit {url} exchange={exchange} queue={queue} bind={bindings}"))

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
                        ch_.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

                ch.basic_qos(prefetch_count=200)
                ch.basic_consume(queue=queue, on_message_callback=on_message)
                ch.start_consuming()
            except pika.exceptions.AMQPConnectionError as e:
                log.error("Rabbit reconnect in 3s due to: %s", e)
                time.sleep(3)
                continue
