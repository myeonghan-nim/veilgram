from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings

from audits.models import AuditLog


class Command(BaseCommand):
    help = "Delete audit logs older than AUDIT_RETENTION_DAYS (default: 90)."

    def handle(self, *args, **options):
        days = getattr(settings, "AUDIT_RETENTION_DAYS", 90)
        cutoff = timezone.now() - timedelta(days=days)
        qs = AuditLog.objects.filter(created_at__lt=cutoff)
        deleted, _ = qs.delete()
        self.stdout.write(self.style.SUCCESS(f"Purged {deleted} old audit logs (cutoff={cutoff.isoformat()})."))
