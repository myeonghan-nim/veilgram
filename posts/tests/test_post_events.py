import pytest

from django.contrib.auth import get_user_model

import posts.signals  # noqa: F401
from notifications.models import Notification, Device, NotificationSetting
from posts.models import Post
from relations.models import Follow

pytestmark = pytest.mark.django_db
User = get_user_model()


class TestPostEventHooks:
    @pytest.fixture(autouse=True)
    def _eager_and_dummy_settings(self, settings):
        settings.CELERY_TASK_ALWAYS_EAGER = True
        settings.PUSH_PROVIDER = "dummy"
        settings.EVENT_BUS_BACKEND = "dummy"

    @pytest.fixture
    def users(self):
        author = User.objects.create()
        follower = User.objects.create()
        outsider = User.objects.create()
        return author, follower, outsider

    def test_post_created_emits_bus_and_notifies_followers(self, users, monkeypatch):
        author, follower, _ = users
        Follow.objects.create(follower=follower, following=author)
        Device.objects.create(user=follower, platform="android", device_token="tok-f1")
        NotificationSetting.objects.get_or_create(user=follower)

        captured = []

        def fake_publish(event, payload, key=None):
            captured.append((event, payload))

        monkeypatch.setattr("posts.tasks.publish_event", fake_publish)

        # 포스트 생성 → 시그널 → Celery 태스크 → 버스 발행 + 알림 fan-out
        p = Post.objects.create(author=author, content="hello world")

        # 버스 이벤트 확인
        assert any(e == "PostCreated" and d.get("post_id") == str(p.id) for e, d in captured)

        # 알림 인앱 생성 확인(팔로워에게 1건 이상)
        assert Notification.objects.filter(user=follower, type="post").exists()

    def test_post_deleted_emits_bus(self, users, monkeypatch):
        author, follower, _ = users
        p = Post.objects.create(author=author, content="to be deleted")

        captured = []
        monkeypatch.setattr("posts.tasks.publish_event", lambda e, d, key=None: captured.append((e, d)))
        post_id = str(p.id)

        # 삭제 → 시그널 → Celery 태스크 → 버스 발행
        p.delete()

        assert any(e == "PostDeleted" and d.get("post_id") == str(post_id) for e, d in captured)
