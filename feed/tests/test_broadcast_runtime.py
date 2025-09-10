import json
import uuid as _uuid

import pytest
from django.contrib.auth import get_user_model

from relations.models import Follow
from realtime.groups import user_feed_group

pytestmark = pytest.mark.django_db
User = get_user_model()


# ---------- 더미 채널 레이어 ----------
class DummyLayer:
    """get_channel_layer() 대체: group_send 호출 캡처"""

    def __init__(self):
        self.sent = []  # list[(group_name, message_dict)]

    async def group_send(self, group, message):
        self.sent.append((group, message))


class BaseBroadcastTest:
    @pytest.fixture
    def author_and_follower(self):
        author = User.objects.create()
        follower = User.objects.create()
        Follow.objects.create(follower=follower, following=author)
        return author, follower

    @pytest.fixture
    def dummy_layer(self, monkeypatch):
        # feed.broadcast 모듈의 get_channel_layer를 더미로 교체
        import feed.broadcast as bc

        dummy = DummyLayer()
        monkeypatch.setattr(bc, "get_channel_layer", lambda: dummy)
        return dummy


class TestBroadcastUtil(BaseBroadcastTest):
    def test_broadcast_user_feed_sends_to_correct_group(self, dummy_layer):
        from feed.broadcast import broadcast_user_feed

        uid = str(_uuid.uuid4())

        broadcast_user_feed([uid], {"kind": "FeedUpdated", "post_id": "p1"})
        assert dummy_layer.sent, "group_send should be called"

        group, msg = dummy_layer.sent[0]
        assert group == user_feed_group(uid)  # 그룹 규칙 일치
        assert msg["type"] == "feed.update"  # 컨슈머 핸들러와 일치
        assert msg["payload"]["kind"] == "FeedUpdated"


class TestEventRuntimeHooks(BaseBroadcastTest):
    @pytest.fixture(autouse=True)
    def _patch_channel_layer(self, monkeypatch, dummy_layer):
        # runtime 내부에서 사용하는 broadcast 모듈도 같은 더미를 보도록 패치
        import feed.broadcast as bc

        monkeypatch.setattr(bc, "get_channel_layer", lambda: dummy_layer)

    def test_handle_message_dispatch_and_broadcast_post_created(self, author_and_follower, monkeypatch, dummy_layer):
        author, follower = author_and_follower

        # 디스패처가 실제 서비스 함수를 호출하지 않아도 되게 더미로 치환(호출 여부만 검증)
        import feed.event_dispather as disp

        called = {}
        monkeypatch.setattr(disp, "dispatch", lambda evt: called.setdefault(evt["type"], 0) or called.update({evt["type"]: 1}))

        # 런타임 호출
        from feed.event_consumer_runtime import handle_message

        evt = {"type": "PostCreated", "payload": {"post_id": str(_uuid.uuid4()), "author_id": str(author.id), "created_ms": 1_700_000_000_000, "hashtags": []}}
        handle_message(json.dumps(evt))

        # 디스패처가 불렸는지
        assert called.get("PostCreated") == 1

        # 팔로워 그룹으로 브로드캐스트 되었는지
        assert dummy_layer.sent, "broadcast missing"
        groups = [g for g, _ in dummy_layer.sent]
        assert user_feed_group(str(follower.id)) in groups

        # 메시지 타입/페이로드 검증
        _, msg = dummy_layer.sent[0]
        assert msg["type"] == "feed.update"
        assert msg["payload"]["kind"] in ("FeedUpdated", "FeedPruned")  # PostCreated면 FeedUpdated

    def test_handle_message_no_broadcast_for_hashtags_extracted(self, author_and_follower, monkeypatch, dummy_layer):
        author, _ = author_and_follower

        import feed.event_dispather as disp

        called = {}
        monkeypatch.setattr(disp, "dispatch", lambda evt: called.setdefault(evt["type"], 0) or called.update({evt["type"]: 1}))

        from feed.event_consumer_runtime import handle_message

        evt = {"type": "HashtagsExtracted", "payload": {"post_id": str(_uuid.uuid4()), "author_id": str(author.id), "created_ms": 1_700_000_000_000, "hashtags": ["x", "y"]}}
        handle_message(json.dumps(evt))

        # 디스패처는 호출되지만, 브로드캐스트는 없어야 함
        assert called.get("HashtagsExtracted") == 1
        assert dummy_layer.sent == []

    def test_handle_message_broadcast_post_deleted(self, author_and_follower, monkeypatch, dummy_layer):
        author, follower = author_and_follower

        import feed.event_dispather as disp

        monkeypatch.setattr(disp, "dispatch", lambda evt: None)

        from feed.event_consumer_runtime import handle_message

        evt = {"type": "PostDeleted", "payload": {"author_id": str(author.id), "created_ms": 1_700_000_000_000}}
        handle_message(json.dumps(evt))

        assert dummy_layer.sent, "broadcast missing"
        group, msg = dummy_layer.sent[0]
        assert group == user_feed_group(str(follower.id))
        assert msg["type"] == "feed.update"
        assert msg["payload"]["kind"] == "FeedPruned"
