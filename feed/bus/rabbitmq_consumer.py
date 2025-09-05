import json

import pika

from .base import BusConsumer, EventHandler


class RabbitBusConsumer(BusConsumer):
    def __init__(self, url: str, exchange: str, queue: str):
        self._params = pika.URLParameters(url)
        self._exchange = exchange
        self._queue = queue

    def start(self, bindings, handler: EventHandler) -> None:
        conn = pika.BlockingConnection(self._params)
        ch = conn.channel()
        ch.exchange_declare(exchange=self._exchange, exchange_type="topic", durable=True)
        ch.queue_declare(queue=self._queue, durable=True)
        for key in bindings:
            ch.queue_bind(exchange=self._exchange, queue=self._queue, routing_key=key)

        def _on_msg(chan, method, props, body):
            data = json.loads(body.decode("utf-8"))
            evt = {"type": data.get("type"), "payload": data.get("payload", {})}
            handler(evt)
            chan.basic_ack(delivery_tag=method.delivery_tag)

        ch.basic_qos(prefetch_count=100)
        ch.basic_consume(queue=self._queue, on_message_callback=_on_msg)
        ch.start_consuming()
