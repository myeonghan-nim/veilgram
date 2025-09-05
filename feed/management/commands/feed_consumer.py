from django.core.management.base import BaseCommand
from django.conf import settings

from feed.bus.kafka_consumer import KafkaBusConsumer
from feed.bus.rabbitmq_consumer import RabbitBusConsumer
from feed.event_dispatcher import dispatch


class Command(BaseCommand):
    help = "Start Feed Service consumer"

    def handle(self, *args, **options):
        driver = settings.FEED_BUS_DRIVER
        if driver == "kafka":
            consumer = KafkaBusConsumer(settings.FEED_KAFKA_BOOTSTRAP, settings.FEED_KAFKA_GROUP_ID)
            consumer.start(settings.FEED_KAFKA_TOPICS, dispatch)
        elif driver == "rabbitmq":
            consumer = RabbitBusConsumer(settings.FEED_RABBIT_URL, settings.FEED_RABBIT_EXCHANGE, settings.FEED_RABBIT_QUEUE)
            consumer.start(settings.FEED_RABBIT_BINDINGS, dispatch)
        else:
            raise SystemExit(f"Unknown FEED_BUS_DRIVER={driver}")
