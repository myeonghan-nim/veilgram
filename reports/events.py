import json
import logging

logger = logging.getLogger(__name__)


def publish_event(event_name: str, payload: dict) -> None:
    try:
        logger.info("EVENT %s %s", event_name, json.dumps(payload, ensure_ascii=False))
    except Exception:
        logger.exception("Failed to publish event %s", event_name)
