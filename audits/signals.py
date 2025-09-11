from django.contrib.auth import get_user_model
from django.dispatch import Signal, receiver

from .services import write_audit_log
from .utils import sha256_hex

User = get_user_model()

# 제공 인자: action, user_id, target_type, target_id, ip, ua, extra
audit_event = Signal()


@receiver(audit_event)
def _consume_audit_event(sender, **kwargs):
    action = kwargs.get("action")
    user_id = kwargs.get("user_id")
    target_type = kwargs.get("target_type", "")
    target_id = kwargs.get("target_id")
    ip = kwargs.get("ip")
    ua = kwargs.get("ua")
    extra = kwargs.get("extra") or {}

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return

    ip_h = sha256_hex(ip)
    ua_h = sha256_hex(ua)

    write_audit_log(
        action=action,
        user=user,
        target_type=target_type,
        target_id=target_id,
        request=None,
        extra={**extra, "_via": "signal"},
        ip_hash=ip_h,
        ua_hash=ua_h,
    )
