from typing import Optional, Mapping, Union

from django.contrib.auth import get_user_model

from .models import AuditLog, AuditAction
from .utils import hashed_ip_ua_from_request

User = get_user_model()


def write_audit_log(
    *,
    action: Union[str, AuditAction],
    user,
    target_type: str = "",
    target_id: Optional[str] = None,
    request=None,
    extra: Optional[Mapping] = None,
    ip_hash: Optional[str] = None,
    ua_hash: Optional[str] = None,
) -> AuditLog:
    """
    표준 수집 함수.
    - request가 있으면 IP/UA를 해시하여 기본값으로 사용.
    - 명시적으로 ip_hash/ua_hash가 전달되면 그것이 우선한다.
    """
    req_ip_hash, req_ua_hash = hashed_ip_ua_from_request(request) if request is not None else (None, None)
    ip_h = ip_hash if ip_hash is not None else req_ip_hash
    ua_h = ua_hash if ua_hash is not None else req_ua_hash

    return AuditLog.objects.create(
        user=user,
        action=str(action),
        target_type=target_type or "",
        target_id=target_id,
        ip_hash=ip_h,
        ua_hash=ua_h,
        extra=dict(extra or {}),
    )
