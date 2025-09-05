import json

from confluent_kafka import Consumer, KafkaException

from .base import BusConsumer, EventHandler


class KafkaBusConsumer(BusConsumer):
    def __init__(self, bootstrap: str, group_id: str):
        self._consumer = Consumer(
            {
                "bootstrap.servers": bootstrap,
                "group.id": group_id,
                "enable.auto.commit": True,
                "auto.offset.reset": "earliest",
            }
        )

    def start(self, topics, handler: EventHandler) -> None:
        self._consumer.subscribe(list(topics))
        while True:
            msg = self._consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                raise KafkaException(msg.error())
            data = json.loads(msg.value().decode("utf-8"))
            evt = {"type": data.get("type"), "payload": data.get("payload", {})}
            handler(evt)
