from __future__ import annotations

import json
import logging
from typing import Any, Dict

from .event_dispatcher import dispatch

log = logging.getLogger(__name__)
REQUIRED_KEYS = ("type", "payload")


def _parse_message(raw: bytes | str) -> Dict[str, Any]:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    obj = json.loads(raw)
    missing = [k for k in REQUIRED_KEYS if k not in obj]
    if missing:
        raise ValueError(f"invalid event: missing keys {missing}")
    return obj


def handle_message(raw: bytes | str) -> None:
    evt = _parse_message(raw)
    try:
        dispatch(evt)
    except Exception:
        log.exception("search dispatch failed: %s", evt)
