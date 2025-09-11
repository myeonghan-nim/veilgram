import hashlib
from typing import Optional, Tuple

from django.conf import settings


def _salt() -> str:
    # 별도 설정이 없으면 SECRET_KEY 사용 (운영에서는 AUDIT_HASH_SALT 별도 권장)
    return getattr(settings, "AUDIT_HASH_SALT", settings.SECRET_KEY)


def sha256_hex(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return hashlib.sha256(f"{_salt()}::{value}".encode("utf-8")).hexdigest()


def get_client_ip(request) -> Optional[str]:
    if not request:
        return None
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def get_user_agent(request) -> Optional[str]:
    if not request:
        return None
    return request.META.get("HTTP_USER_AGENT")


def hashed_ip_ua_from_request(request) -> Tuple[Optional[str], Optional[str]]:
    ip = get_client_ip(request)
    ua = get_user_agent(request)
    return sha256_hex(ip), sha256_hex(ua)
