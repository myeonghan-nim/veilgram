from django.conf import settings
from django.core.cache import cache
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken

from core.models import DeviceCredential


def _session_key(user_id: str) -> str:
    return f"sessions:{user_id}"


def _refresh_ttl_seconds() -> int:
    lifetime = settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]
    return int(lifetime.total_seconds())


def revoke_all_refresh_tokens(user) -> int:
    count = 0
    for t in OutstandingToken.objects.filter(user=user):
        _, created = BlacklistedToken.objects.get_or_create(token=t)
        if created:
            count += 1
    return count


def enforce_single_device_session(user, current_device_id: str) -> str | None:
    key = _session_key(str(user.id))
    previous_device_id = cache.get(key)
    if getattr(settings, "SESSION_LIMIT_ONE_DEVICE", True):
        if previous_device_id and previous_device_id != current_device_id:
            revoke_all_refresh_tokens(user)
        elif previous_device_id is None:
            exists_other = DeviceCredential.objects.filter(user=user, is_active=True).exclude(device_id=current_device_id).exists()
            if exists_other:
                revoke_all_refresh_tokens(user)
    cache.set(key, current_device_id, timeout=_refresh_ttl_seconds())
    return previous_device_id
