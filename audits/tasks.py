from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import AuditLog


@shared_task
def purge_old_audit_logs():
    days = getattr(settings, "AUDIT_RETENTION_DAYS", 90)
    cutoff = timezone.now() - timedelta(days=days)
    AuditLog.objects.filter(created_at__lt=cutoff).delete()
