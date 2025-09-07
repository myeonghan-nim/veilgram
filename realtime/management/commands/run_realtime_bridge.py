import asyncio
import json
import signal

from django.conf import settings
from django.core.management.base import BaseCommand
from channels.layers import get_channel_layer
from redis.asyncio import Redis

from realtime.groups import user_feed_group


class Command(BaseCommand):
    help = "Bridge Redis Pub/Sub messages to Channels groups"

    async def _run(self):
        redis = Redis.from_url(settings.REDIS_URL)
        pubsub = redis.pubsub()
        await pubsub.subscribe(settings.FEED_UPDATES_CHANNEL)

        channel_layer = get_channel_layer()
        self.stdout.write(self.style.SUCCESS(f"Realtime bridge started. Subscribed: {settings.FEED_UPDATES_CHANNEL}"))

        try:
            async for msg in pubsub.listen():
                if not msg or msg.get("type") != "message":
                    continue

                try:
                    data = json.loads(msg["data"])
                except Exception:
                    continue

                if data.get("type") == "feed_update":
                    payload = data.get("data") or {}
                    user_ids = data.get("user_ids") or []
                    for uid in user_ids:
                        await channel_layer.group_send(user_feed_group(uid), {"type": "feed.update", "payload": payload})
        finally:
            await pubsub.unsubscribe(settings.FEED_UPDATES_CHANNEL)
            await pubsub.close()
            await redis.close()

    def handle(self, *args, **options):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        task = loop.create_task(self._run())

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, task.cancel)

        try:
            loop.run_until_complete(task)
        except asyncio.CancelledError:
            pass
        finally:
            loop.close()
            self.stdout.write(self.style.WARNING("Realtime bridge stopped."))
