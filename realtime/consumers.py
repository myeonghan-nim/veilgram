from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .groups import user_feed_group


class FeedConsumer(AsyncJsonWebsocketConsumer):
    """
    그룹: feed.<user_id>
    group_send 예:
        await channel_layer.group_send(
            f"user_feed_group(user_id)",
            {"type": "feed.update", "payload": {...}}
        )
    """

    async def connect(self):
        self.user_id = self.scope.get("user_id")
        if not self.user_id:
            await self.close(code=4401)  # unauthorized
            return

        self.group_name = user_feed_group(self.user_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if content and content.get("type") == "ping":
            await self.send_json({"event": "pong"})

    async def feed_update(self, event):
        payload = event.get("payload") or {}
        await self.send_json({"event": "feed_update", "data": payload})
