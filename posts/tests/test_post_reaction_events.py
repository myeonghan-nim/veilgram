import pytest
from django.contrib.auth import get_user_model

import posts.signals  # noqa: F401
from posts.models import Post, PostLike, Repost
from notifications.models import Notification, NotificationSetting

pytestmark = pytest.mark.django_db
User = get_user_model()


class BaseEventTest:
    @pytest.fixture(autouse=True)
    def _eager_and_dummy_settings(self, settings):
        # 외부 인프라 의존 제거 + 태스크 동기 실행
        settings.CELERY_TASK_ALWAYS_EAGER = True
        settings.EVENT_BUS_BACKEND = "dummy"
        settings.PUSH_PROVIDER = "dummy"

        try:
            from veilgram.celery import app as celery_app
        except Exception:
            # 프로젝트 루트가 다르다면 현재 앱을 fallback
            from celery import current_app as celery_app

        celery_app.conf.task_always_eager = True
        celery_app.conf.task_eager_propagates = True

    @pytest.fixture
    def users(self):
        author = User.objects.create()
        actor = User.objects.create()  # like/repost 하는 사람
        outsider = User.objects.create()  # 검증에 직접 사용하지 않지만 프레임 유지용
        return author, actor, outsider

    @pytest.fixture
    def post(self, users):
        author, _, _ = users
        return Post.objects.create(author=author, content="hello world")


class TestPostLikeEvents(BaseEventTest):
    def test_post_like_emits_bus_and_notifies_author(self, users, post, monkeypatch):
        author, actor, _ = users
        # 작성자가 'like' 알림 허용
        NotificationSetting.objects.update_or_create(user=author, defaults={"like": True})

        captured = []

        def fake_publish(event, payload, key=None):
            captured.append((event, payload, key))

        # 버스 발행 가로채기
        monkeypatch.setattr("posts.tasks.publish_event", fake_publish)

        # 생성 → 시그널 → Celery 태스크 → 버스 발행 + 알림 생성
        like = PostLike.objects.create(user=actor, post=post)

        # 버스 이벤트 검증
        assert any(e == "PostLiked" and d.get("post_id") == str(post.id) and d.get("actor_id") == str(actor.id) and d.get("author_id") == str(author.id) for (e, d, _) in captured)

        # 인앱 알림 생성(작성자에게 like 타입)
        assert Notification.objects.filter(user=author, type="like", payload__post_id=str(post.id)).exists()

    def test_post_unlike_emits_bus_without_new_notification(self, users, post, monkeypatch):
        author, actor, _ = users
        NotificationSetting.objects.update_or_create(user=author, defaults={"like": True})

        # 선행 like(생성 이벤트로 알림 1건 생길 수 있음)
        like = PostLike.objects.create(user=actor, post=post)
        before = Notification.objects.filter(user=author, type="like").count()

        captured = []
        monkeypatch.setattr("posts.tasks.publish_event", lambda e, d, key=None: captured.append((e, d, key)))

        # 삭제 → 시그널 → Celery 태스크 → 버스 발행(알림은 일반적으로 미발송)
        like.delete()

        # 버스 이벤트 검증
        assert any(
            e == "PostUnliked" and d.get("post_id") == str(post.id) and d.get("actor_id") == str(actor.id) and d.get("author_id") == str(author.id) for (e, d, _) in captured
        )

        # 새 알림은 생기지 않아야 함
        after = Notification.objects.filter(user=author, type="like").count()
        assert after == before


class TestRepostEvents(BaseEventTest):
    def test_repost_emits_bus_and_notifies_author(self, users, post, monkeypatch):
        author, actor, _ = users
        # 리포스트 알림은 posts.tasks에서 type_='post'로 매핑 → 'post' 허용 필요
        NotificationSetting.objects.update_or_create(user=author, defaults={"post": True})

        captured = []

        def fake_publish(event, payload, key=None):
            captured.append((event, payload, key))

        monkeypatch.setattr("posts.tasks.publish_event", fake_publish)

        # 생성 → 시그널 → Celery 태스크 → 버스 발행 + 알림 생성
        rp = Repost.objects.create(user=actor, original_post=post)

        # 버스 이벤트 검증
        assert any(
            e == "PostReposted"
            and d.get("post_id") == str(post.id)
            and d.get("actor_id") == str(actor.id)
            and d.get("author_id") == str(author.id)
            and d.get("repost_id")  # 존재 여부만 확인
            for (e, d, _) in captured
        )

        # 인앱 알림 생성(작성자에게 post 타입으로 매핑)
        assert Notification.objects.filter(user=author, type="post", payload__post_id=str(post.id)).exists()

    def test_unrepost_emits_bus_without_new_notification(self, users, post, monkeypatch):
        author, actor, _ = users
        NotificationSetting.objects.update_or_create(user=author, defaults={"post": True})

        rp = Repost.objects.create(user=actor, original_post=post)
        before = Notification.objects.filter(user=author, type="post").count()

        captured = []
        monkeypatch.setattr("posts.tasks.publish_event", lambda e, d, key=None: captured.append((e, d, key)))

        # 삭제 → 시그널 → Celery 태스크 → 버스 발행
        rp.delete()

        assert any(
            e == "PostUnreposted" and d.get("post_id") == str(post.id) and d.get("actor_id") == str(actor.id) and d.get("author_id") == str(author.id) for (e, d, _) in captured
        )

        # 새 알림은 생기지 않아야 함
        after = Notification.objects.filter(user=author, type="post").count()
        assert after == before
