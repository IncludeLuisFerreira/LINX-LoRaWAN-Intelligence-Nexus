import json
import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def _reject_constant(value: str) -> Any:
    raise ValueError(f"constante JSON não permitida: {value}")


@dataclass(frozen=True)
class TopicParts:
    app_id: str
    dev_eui: str
    event_type: str


@dataclass(frozen=True)
class ValidUplink:
    app_id: str
    dev_eui: str
    event_type: str
    event: dict[str, Any]


def parse_topic(topic: str) -> TopicParts | None:
    segments = topic.split("/")
    if len(segments) != 6:
        return None
    if segments[0] != "application":
        return None
    if segments[2] != "device":
        return None
    if segments[4] != "event":
        return None
    app_id, dev_eui, event_type = segments[1], segments[3], segments[5]
    if not all(
        _SEGMENT_PATTERN.match(part) for part in (app_id, dev_eui, event_type)
    ):
        return None
    return TopicParts(app_id, dev_eui, event_type)


def _identity_mismatch(event: dict[str, Any], parts: TopicParts) -> bool:
    device_info = event.get("deviceInfo")
    if not isinstance(device_info, dict):
        return False
    body_dev_eui = device_info.get("devEui")
    if isinstance(body_dev_eui, str) and body_dev_eui:
        if body_dev_eui.lower() != parts.dev_eui.lower():
            return True
    body_app_id = device_info.get("applicationId")
    if isinstance(body_app_id, str) and body_app_id:
        if body_app_id.lower() != parts.app_id.lower():
            return True
    return False


def validate_message(
    topic: str, raw: bytes, max_bytes: int
) -> ValidUplink | None:
    if len(raw) > max_bytes:
        logger.warning(
            "payload excede o tamanho máximo permitido (%d > %d)",
            len(raw),
            max_bytes,
        )
        return None

    parts = parse_topic(topic)
    if parts is None:
        logger.warning("tópico inválido: %r", topic)
        return None

    try:
        event = json.loads(raw.decode(), parse_constant=_reject_constant)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        logger.warning("payload JSON inválido no tópico %r", topic)
        return None

    if not isinstance(event, dict):
        logger.warning("payload JSON não é um objeto no tópico %r", topic)
        return None

    obj = event.get("object")
    if not isinstance(obj, dict):
        logger.warning(
            "campo 'object' ausente ou inválido no tópico %r", topic
        )
        return None

    timestamp = event.get("time")
    if not isinstance(timestamp, str) or not timestamp:
        logger.warning("campo 'time' ausente ou inválido no tópico %r", topic)
        return None

    if _identity_mismatch(event, parts):
        logger.warning(
            "identidade do corpo diverge do tópico %r; descartado", topic
        )
        return None

    return ValidUplink(
        app_id=parts.app_id,
        dev_eui=parts.dev_eui,
        event_type=parts.event_type,
        event=event,
    )
