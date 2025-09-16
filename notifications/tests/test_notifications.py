import uuid

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from notifications.models import Device, Notification, NotificationSetting
from notifications.tasks import fanout_post_created, single_user_push

pytestmark = pytest.mark.django_db
User = get_user_model()


# ---------- Fixtures ----------
@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def users():
    a = User.objects.create()
    b = User.objects.create()
    c = User.objects.create()
    return a, b, c  # a follows b, c is irrelevant


@pytest.fixture
def follow(users):
    a, b, c = users
    from relations.models import Follow

    Follow.objects.create(follower=a, following=b)
    return a, b


@pytest.fixture
def auth_client(client, users):
    u, _, _ = users
    client.force_authenticate(u)
    return client, u


# =======================
# Devices API
# =======================
class TestDevicesAPI:
    # 푸시 대상 엔드포인트(디바이스 토큰) 등록/조회/비활성화 API

    def test_register_and_list(self, auth_client):
        client, u = auth_client
        url = "/api/v1/notifications/devices/"

        body = {"platform": "android", "device_token": "tok-1"}
        r = client.post(url, data=body, format="json")
        assert r.status_code == 201

        assert Device.objects.filter(user=u, device_token="tok-1", is_active=True).exists()

        r2 = client.get(url)
        assert r2.status_code == 200

        data = r2.json()
        assert isinstance(data, list) and data[0]["device_token"] == "tok-1"

    def test_delete_means_soft_deactivate(self, auth_client):
        client, u = auth_client
        url = "/api/v1/notifications/devices/"

        # 등록
        r = client.post(url, data={"platform": "android", "device_token": "tok-del"}, format="json")
        assert r.status_code == 201

        dev_id = r.json()["id"]
        # 삭제(비활성화)
        r2 = client.delete(f"{url}{dev_id}/")
        assert r2.status_code == 204

        dev = Device.objects.get(id=dev_id)
        assert dev.is_active is False


# =======================
# Notification Settings API
# =======================
class TestNotificationSettingsAPI:
    # 알림 설정 조회/수정

    def test_auto_create_and_get(self, auth_client):
        client, u = auth_client
        url = "/api/v1/notifications/settings"

        r1 = client.get(url)
        assert r1.status_code == 200  # get_or_create 동작

        s = NotificationSetting.objects.get(user=u)
        # 기본값 True로 생성되었는지 정도만 확인
        assert s.post is True and s.like is True and s.comment is True and s.follow is True

    def test_update_partial_fields(self, auth_client):
        client, u = auth_client
        url = "/api/v1/notifications/settings"

        # 일부 필드만 수정
        r2 = client.put(url, data={"post": False, "like": True}, format="json")
        assert r2.status_code == 200

        s = NotificationSetting.objects.get(user=u)
        assert s.post is False and s.like is True


# =======================
# Notifications API (list / mark_read)
# =======================
class TestNotificationsAPI:
    # 인앱 알림 목록/읽음 처리

    def test_mark_read_batch(self, auth_client):
        client, u = auth_client

        n1 = Notification.objects.create(user=u, type="like", payload={"post_id": "x"})
        n2 = Notification.objects.create(user=u, type="comment", payload={"post_id": "x"})

        url = "/api/v1/notifications/mark_read/"
        r = client.post(url, data={"ids": [str(n1.id), str(n2.id)]}, format="json")
        assert r.status_code == 200 and r.json()["updated"] == 2

        assert Notification.objects.filter(user=u, is_read=True).count() == 2

    def test_list_filter_by_read_flag(self, auth_client):
        client, u = auth_client
        Notification.objects.create(user=u, type="post", payload={}, is_read=False)
        Notification.objects.create(user=u, type="comment", payload={}, is_read=True)

        url = "/api/v1/notifications/"
        r_unread = client.get(url, {"read": "false"})
        r_read = client.get(url, {"read": "true"})
        assert r_unread.status_code == 200 and r_read.status_code == 200

        assert all(item["is_read"] is False for item in r_unread.json())
        assert all(item["is_read"] is True for item in r_read.json())


# =======================
# Celery Tasks (fan-out / single)
# =======================
class TestNotificationTasks:
    # Celery 태스크 동작 검증: 외부 연동 없이 결정적으로 테스트하기 위해 dummy provider + eager 실행

    @pytest.fixture(autouse=True)
    def _force_dummy_provider_and_eager(self, settings):
        # 이 클래스의 모든 테스트에 자동 적용
        settings.PUSH_PROVIDER = "dummy"
        settings.CELERY_TASK_ALWAYS_EAGER = True

    def test_fanout_post_created_sends_to_followers(self, users, follow):
        a, b, _ = users  # a follows b
        # a의 디바이스 & 설정
        Device.objects.create(user=a, platform="android", device_token="tok-a1")
        NotificationSetting.objects.get_or_create(user=a)  # 기본 True

        sent = fanout_post_created(author_id=str(b.id), post_id=str(uuid.uuid4()), title="T", body="B")
        assert sent == 1
        assert Notification.objects.filter(user=a, type="post").exists()

    def test_respects_opt_out(self, users):
        a, b, _ = users
        from relations.models import Follow

        Follow.objects.create(follower=a, following=b)

        Device.objects.create(user=a, platform="android", device_token="tok-a1")
        NotificationSetting.objects.update_or_create(user=a, defaults={"post": False})

        sent = fanout_post_created(author_id=str(b.id), post_id=str(uuid.uuid4()), title="T", body="B")
        assert sent == 0
        assert not Notification.objects.filter(user=a, type="post").exists()

    def test_single_user_push_generic(self, users):
        # 개별 유저에게 단일 타입 푸시/인앱 저장
        a, _, _ = users
        Device.objects.create(user=a, platform="android", device_token="tok-z1")
        NotificationSetting.objects.get_or_create(user=a)

        ok = single_user_push(user_id=str(a.id), type_="like", title="Liked", body="Your post got a like", data={"post_id": "p1"})
        assert ok == 1

        saved = Notification.objects.filter(user=a, type="like").first()
        assert saved and saved.payload.get("post_id") == "p1"
