import logging
from typing import Any, Dict

from django.conf import settings
from django.dispatch import Signal
from django.utils.module_loading import import_string

log = logging.getLogger(__name__)

# ---- Domain signals (WIP) ----
user_followed = Signal()  # kwargs: follower_id, following_id
user_unfollowed = Signal()  # kwargs: follower_id, following_id
user_blocked = Signal()  # kwargs: user_id, blocked_user_id
user_unblocked = Signal()  # kwargs: user_id, blocked_user_id


# ---- Pluggable emitter (out-of-process bus) ----
def _get_emitter():
    path = getattr(settings, "RELATIONS_EVENT_EMITTER", None)
    if not path:
        return logging_emitter
    try:
        return import_string(path)
    except Exception:
        log.exception("Failed to import emitter '%s'; fallback to logging.", path)
        return logging_emitter


def logging_emitter(event: str, payload: Dict[str, Any]) -> None:
    log.info("EVENT %s %s", event, payload)


def emit(event: str, payload: Dict[str, Any]) -> None:
    # 1) in-process signal (for local subscribers)
    sig = {"UserFollowed": user_followed, "UserUnfollowed": user_unfollowed, "UserBlocked": user_blocked, "UserUnblocked": user_unblocked}.get(event)
    if sig:
        sig.send(sender="relations", **payload)

    # 2) out-of-process emitter (Bus/Celery/etc.)
    try:
        _get_emitter()(event, payload)
    except Exception:
        log.exception("Emitter failed for %s", event)


# ---- Convenience helpers ----
def emit_user_followed(follower_id, following_id):
    emit("UserFollowed", {"follower_id": str(follower_id), "following_id": str(following_id)})


def emit_user_unfollowed(follower_id, following_id):
    emit("UserUnfollowed", {"follower_id": str(follower_id), "following_id": str(following_id)})


def emit_user_blocked(user_id, blocked_user_id):
    emit("UserBlocked", {"user_id": str(user_id), "blocked_user_id": str(blocked_user_id)})


def emit_user_unblocked(user_id, blocked_user_id):
    emit("UserUnblocked", {"user_id": str(user_id), "blocked_user_id": str(blocked_user_id)})


# ---- Optional: Celery emitter (use by settings) ----
def celery_emitter(event: str, payload: Dict[str, Any]) -> None:
    # Import only when configured to avoid hard dependency
    from .tasks import publish_relation_event

    publish_relation_event.delay(event, payload)
