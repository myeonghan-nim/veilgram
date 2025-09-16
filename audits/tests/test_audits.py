import uuid
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from audits.models import AuditAction, AuditLog
from audits.services import write_audit_log
from audits.signals import audit_event

User = get_user_model()


@pytest.mark.django_db
class TestAuditLogs:
    def _mk_user(self, nick="u1"):
        # 프로젝트 사용자 생성 방식에 맞춰 최소 필드만
        return User.objects.create()

    def test_write_and_list_self(self):
        u = self._mk_user()
        client = APIClient()
        client.force_authenticate(user=u)

        log = write_audit_log(action=AuditAction.LOGIN, user=u, target_type="user", target_id=str(u.id), request=None, extra={"from": "unit"})
        assert AuditLog.objects.filter(id=log.id).exists()

        resp = client.get("/api/v1/audits/logs/")
        assert resp.status_code == 200

        body = resp.json()
        assert len(body) >= 1

        ids = [item["id"] for item in body]
        assert str(log.id) in ids

    def test_visibility_non_staff_sees_only_own(self):
        a = self._mk_user("a")
        b = self._mk_user("b")
        write_audit_log(action=AuditAction.FOLLOW, user=a, target_type="user", target_id=str(b.id))
        write_audit_log(action=AuditAction.FOLLOW, user=b, target_type="user", target_id=str(a.id))

        client = APIClient()
        client.force_authenticate(user=a)
        resp = client.get("/api/v1/audits/logs/")
        assert resp.status_code == 200
        for item in resp.json():
            assert item["user"] == str(a.id)

    def test_staff_can_filter_user_id(self):
        admin = self._mk_user("admin")
        admin.is_superuser = True
        admin.save()
        u = self._mk_user("u")
        write_audit_log(action=AuditAction.CREATE_POST, user=u, target_type="post", target_id=str(uuid.uuid4()))

        client = APIClient()
        client.force_authenticate(user=admin)
        resp = client.get(f"/api/v1/audits/logs/?user_id={u.id}")
        assert resp.status_code == 200
        assert all(item["user"] == str(u.id) for item in resp.json())

    def test_signal_emits_and_hashes(self):
        u = self._mk_user("sig")
        audit_event.send(sender=None, action=AuditAction.LOGIN, user_id=u.id, target_type="user", target_id=u.id, ip="203.0.113.10", ua="pytest-ua", extra={"k": "v"})
        row = AuditLog.objects.filter(user=u, action=AuditAction.LOGIN).latest("created_at")
        assert row.ip_hash and row.ua_hash
        assert row.ip_hash != "203.0.113.10" and row.ua_hash != "pytest-ua"

    def test_purge_management_command(self):
        u = self._mk_user("old")
        row = write_audit_log(action=AuditAction.LOGOUT, user=u)
        # created_at은 auto_add이므로 update로 과거로 밀어넣는다
        AuditLog.objects.filter(pk=row.pk).update(created_at=timezone.now() - timedelta(days=120))

        call_command("purge_audit_logs")
        assert not AuditLog.objects.filter(pk=row.pk).exists()
