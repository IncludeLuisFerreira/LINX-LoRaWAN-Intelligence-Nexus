import json
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


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
    if not app_id or not dev_eui or not event_type:
        return None
    return TopicParts(app_id, dev_eui, event_type)


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
        event = json.loads(raw.decode())
    except (json.JSONDecodeError, UnicodeDecodeError):
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

    if "time" not in event:
        logger.warning("campo 'time' ausente no tópico %r", topic)
        return None

    return ValidUplink(
        app_id=parts.app_id,
        dev_eui=parts.dev_eui,
        event_type=parts.event_type,
        event=event,
    )
