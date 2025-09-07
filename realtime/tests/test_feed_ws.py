import pytest

from django.contrib.auth import get_user_model
from channels.testing import WebsocketCommunicator
from channels.layers import get_channel_layer
from rest_framework_simplejwt.tokens import AccessToken

from realtime.groups import user_feed_group
from veilgram.asgi import application

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.asyncio
class TestFeedWebSocket:
    # ---- Utility ----
    @staticmethod
    def _make_access_token(user_id):
        t = AccessToken()
        # SimpleJWT 기본(user_id)과 커스텀(sub) 모두 채워 어떤 해석기라도 통과
        t["user_id"] = str(user_id)
        t["sub"] = str(user_id)
        return str(t)

    # ---- Fixture ----
    @pytest.fixture(autouse=True)
    def in_memory_channel_layer(self, settings):
        # 테스트에서 Redis를 사용하지 않도록 Channels 레이어를 in-memory로 덮어쓰기
        settings.CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

    @pytest.fixture
    def user(self):
        User = get_user_model()
        # UUID PK만으로 생성 가능한 최소 유저 (프로젝트 사용자 모델 가정)
        return User.objects.create()

    # ---- Testcase ----
    async def test_reject_without_token(self, user):
        comm = WebsocketCommunicator(application, "/ws/feed/")
        connected, code = await comm.connect()
        assert connected is False
        assert code == 4401  # unauthorized

    async def test_reject_with_invalid_token(self, user):
        comm = WebsocketCommunicator(application, "/ws/feed/?token=NOT.A.JWT")
        connected, code = await comm.connect()
        assert connected is False
        assert code == 4401

    async def test_auth_via_query_string_and_receive_group_message(self, user):
        token = self._make_access_token(user.id)
        comm = WebsocketCommunicator(application, f"/ws/feed/?token={token}")
        connected, _ = await comm.connect()
        assert connected is True

        # group fan-out 시뮬레이션
        channel_layer = get_channel_layer()
        await channel_layer.group_send(user_feed_group(str(user.id)), {"type": "feed.update", "payload": {"post_id": "P1", "reason": "new_post"}})

        msg = await comm.receive_json_from(timeout=1)
        assert msg["event"] == "feed_update"
        assert msg["data"]["post_id"] == "P1"

        await comm.disconnect()

    async def test_auth_via_sec_websocket_protocol_and_receive(self, user):
        # 헤더 경로 (Sec-WebSocket-Protocol) 인증
        token = self._make_access_token(user.id)
        # subprotocols 인자로 넣으면 communicator가 Sec-WebSocket-Protocol 헤더를 세팅
        comm = WebsocketCommunicator(application, "/ws/feed/", subprotocols=[token])
        connected, _ = await comm.connect()
        assert connected is True

        channel_layer = get_channel_layer()
        await channel_layer.group_send(user_feed_group(str(user.id)), {"type": "feed.update", "payload": {"post_id": "P2", "reason": "new_post"}})

        msg = await comm.receive_json_from(timeout=1)
        assert msg["event"] == "feed_update"
        assert msg["data"]["post_id"] == "P2"

        await comm.disconnect()

    async def test_ping_pong(self, user):
        token = self._make_access_token(user.id)
        comm = WebsocketCommunicator(application, f"/ws/feed/?token={token}")
        connected, _ = await comm.connect()
        assert connected is True

        await comm.send_json_to({"type": "ping"})
        pong = await comm.receive_json_from(timeout=1)
        assert pong == {"event": "pong"}

        await comm.disconnect()
