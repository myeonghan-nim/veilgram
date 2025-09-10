import pytest
from django.contrib.auth import get_user_model

# AppConfig.ready() 보장 + 테스트 안정성 위해 명시 임포트
import comments.signals  # noqa: F401
from posts.models import Post
from comments.models import Comment
from notifications.models import Notification, NotificationSetting

pytestmark = pytest.mark.django_db
User = get_user_model()


class BaseCommentEventTest:
    @pytest.fixture(autouse=True)
    def _eager_and_dummy_settings(self, settings):
        settings.CELERY_TASK_ALWAYS_EAGER = True
        settings.EVENT_BUS_BACKEND = "dummy"
        settings.PUSH_PROVIDER = "dummy"

    @pytest.fixture
    def users(self):
        post_author = User.objects.create()
        commenter = User.objects.create()
        parent_author = User.objects.create()
        return post_author, commenter, parent_author

    @pytest.fixture
    def post(self, users):
        post_author, _, _ = users
        return Post.objects.create(author=post_author, content="hello")


class TestCommentCreated(BaseCommentEventTest):
    def test_comment_created_emits_bus_and_notifies_post_author(self, users, post, monkeypatch):
        post_author, commenter, _ = users
        NotificationSetting.objects.update_or_create(user=post_author, defaults={"comment": True})

        captured = []
        monkeypatch.setattr("comments.tasks.publish_event", lambda e, d, key=None: captured.append((e, d, key)))

        c = Comment.objects.create(user=commenter, post=post, content="hi")

        assert any(
            e == "CommentCreated" and d.get("comment_id") == str(c.id) and d.get("post_id") == str(post.id) and d.get("author_id") == str(commenter.id) for (e, d, _) in captured
        )
        assert Notification.objects.filter(user=post_author, type="comment", payload__comment_id=str(c.id)).exists()

    def test_reply_notifies_parent_author_and_post_author_once_each(self, users, post, monkeypatch):
        post_author, commenter, parent_author = users
        NotificationSetting.objects.update_or_create(user=post_author, defaults={"comment": True})
        NotificationSetting.objects.update_or_create(user=parent_author, defaults={"comment": True})

        parent = Comment.objects.create(user=parent_author, post=post, content="parent")
        before_post_author = Notification.objects.filter(user=post_author, type="comment").count()
        before_parent_author = Notification.objects.filter(user=parent_author, type="comment").count()

        captured = []
        monkeypatch.setattr("comments.tasks.publish_event", lambda e, d, key=None: captured.append((e, d, key)))

        child = Comment.objects.create(user=commenter, post=post, parent=parent, content="child")

        # 버스 이벤트
        assert any(e == "CommentCreated" and d.get("comment_id") == str(child.id) for (e, d, _) in captured)

        # 두 명에게 각 1건씩 증가 (중복 없이)
        assert Notification.objects.filter(user=post_author, type="comment").count() == before_post_author + 1
        assert Notification.objects.filter(user=parent_author, type="comment").count() == before_parent_author + 1

    def test_self_comment_no_notification(self, users, post, monkeypatch):
        post_author, _, _ = users
        NotificationSetting.objects.update_or_create(user=post_author, defaults={"comment": True})

        captured = []
        monkeypatch.setattr("comments.tasks.publish_event", lambda e, d, key=None: captured.append((e, d, key)))

        c = Comment.objects.create(user=post_author, post=post, content="self")

        assert any(e == "CommentCreated" and d.get("comment_id") == str(c.id) for (e, d, _) in captured)
        # 본인에게는 알림 없음
        assert not Notification.objects.filter(user=post_author, type="comment", payload__comment_id=str(c.id)).exists()

    def test_opt_out_respected(self, users, post, monkeypatch):
        post_author, commenter, _ = users
        NotificationSetting.objects.update_or_create(user=post_author, defaults={"comment": False})

        captured = []
        monkeypatch.setattr("comments.tasks.publish_event", lambda e, d, key=None: captured.append((e, d, key)))

        c = Comment.objects.create(user=commenter, post=post, content="hi")

        assert any(e == "CommentCreated" and d.get("comment_id") == str(c.id) for (e, d, _) in captured)
        # opt-out 이므로 인앱 알림이 생성되지 않음
        assert not Notification.objects.filter(user=post_author, type="comment", payload__comment_id=str(c.id)).exists()


class TestCommentUpdatedDeleted(BaseCommentEventTest):
    def test_comment_deleted_emits_bus(self, users, post, monkeypatch):
        post_author, commenter, _ = users
        c = Comment.objects.create(user=commenter, post=post, content="to be deleted")

        captured = []
        monkeypatch.setattr("comments.tasks.publish_event", lambda e, d, key=None: captured.append((e, d, key)))

        comment_id = str(c.id)  # delete() 후 pk None 방지
        c.delete()

        assert any(e == "CommentDeleted" and d.get("comment_id") == comment_id for (e, d, _) in captured)

    def test_comment_updated_emits_bus(self, users, post, monkeypatch):
        post_author, commenter, _ = users
        c = Comment.objects.create(user=commenter, post=post, content="old")

        captured = []
        monkeypatch.setattr("comments.tasks.publish_event", lambda e, d, key=None: captured.append((e, d, key)))

        # 간단한 업데이트 시나리오 (예: content 변경 후 save)
        c.content = "new"
        c.save(update_fields=["content"])

        assert any(e == "CommentUpdated" and d.get("comment_id") == str(c.id) for (e, d, _) in captured)
