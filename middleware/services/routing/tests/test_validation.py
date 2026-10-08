import json

from routing.validation import TopicParts, parse_topic, validate_message


def _raw(event: dict) -> bytes:
    return json.dumps(event).encode()


_VALID = {"object": {"t": 20}, "time": "2026-10-08T12:00:00Z"}
_TOPIC = "application/app1/device/devA/event/up"


def test_parse_topic_valid():
    assert parse_topic(_TOPIC) == TopicParts("app1", "devA", "up")


def test_parse_topic_rejects_bad_segments():
    assert parse_topic("other/app1/device/devA/event/up") is None
    assert parse_topic("application/app1/other/devA/event/up") is None
    assert parse_topic("application/app1/device/devA/other/up") is None
    assert parse_topic("application/app1/device/devA/event") is None
    assert parse_topic("application/app1/device/devA/event/up/extra") is None
    assert parse_topic("") is None


def test_validate_message_ok():
    uplink = validate_message(_TOPIC, _raw(_VALID), max_bytes=65536)

    assert uplink is not None
    assert uplink.app_id == "app1"
    assert uplink.dev_eui == "devA"
    assert uplink.event_type == "up"
    assert uplink.event == _VALID


def test_validate_message_drops_oversize(caplog):
    with caplog.at_level("WARNING"):
        assert validate_message(_TOPIC, b"x" * 11, max_bytes=10) is None
    assert "payload" in caplog.text


def test_validate_message_accepts_exactly_at_limit():
    raw = _raw(_VALID)
    assert validate_message(_TOPIC, raw, max_bytes=len(raw)) is not None


def test_validate_message_drops_invalid_json(caplog):
    with caplog.at_level("WARNING"):
        assert validate_message(_TOPIC, b"not-json", max_bytes=65536) is None
    assert "inválido" in caplog.text


def test_validate_message_drops_non_utf8(caplog):
    with caplog.at_level("WARNING"):
        assert validate_message(_TOPIC, b"\xff\xfe", max_bytes=65536) is None


def test_validate_message_drops_non_object_json(caplog):
    with caplog.at_level("WARNING"):
        assert validate_message(_TOPIC, b"[1, 2]", max_bytes=65536) is None


def test_validate_message_drops_bad_topic():
    assert (
        validate_message("weird/topic", _raw(_VALID), max_bytes=65536) is None
    )


def test_validate_message_drops_missing_object(caplog):
    with caplog.at_level("WARNING"):
        assert (
            validate_message(_TOPIC, _raw({"time": "t"}), max_bytes=65536)
            is None
        )


def test_validate_message_drops_non_dict_object(caplog):
    with caplog.at_level("WARNING"):
        assert (
            validate_message(
                _TOPIC, _raw({"object": "x", "time": "t"}), max_bytes=65536
            )
            is None
        )


def test_validate_message_drops_missing_timestamp(caplog):
    with caplog.at_level("WARNING"):
        assert (
            validate_message(_TOPIC, _raw({"object": {}}), max_bytes=65536)
            is None
        )


def test_validate_message_drops_null_timestamp(caplog):
    with caplog.at_level("WARNING"):
        assert (
            validate_message(
                _TOPIC,
                _raw({"object": {}, "time": None}),
                max_bytes=65536,
            )
            is None
        )


def test_validate_message_drops_non_string_timestamp(caplog):
    with caplog.at_level("WARNING"):
        assert (
            validate_message(
                _TOPIC, _raw({"object": {}, "time": 123}), max_bytes=65536
            )
            is None
        )


def test_parse_topic_rejects_segment_with_dot():
    assert parse_topic("application/a.pp/device/devA/event/up") is None
    assert parse_topic("application/app1/device/de.v/event/up") is None
    assert parse_topic("application/app1/device/devA/event/up!") is None


def test_parse_topic_accepts_allowed_segment_chars():
    assert parse_topic("application/app-1_x/device/devA/event/up") == (
        TopicParts("app-1_x", "devA", "up")
    )


def test_validate_message_drops_identity_mismatch_dev_eui(caplog):
    event = {
        "object": {"t": 20},
        "time": "t",
        "deviceInfo": {"devEui": "other"},
    }

    with caplog.at_level("WARNING"):
        assert validate_message(_TOPIC, _raw(event), max_bytes=65536) is None

    assert "diverge" in caplog.text


def test_validate_message_drops_identity_mismatch_app_id(caplog):
    event = {
        "object": {"t": 20},
        "time": "t",
        "deviceInfo": {"applicationId": "other-app"},
    }

    with caplog.at_level("WARNING"):
        assert validate_message(_TOPIC, _raw(event), max_bytes=65536) is None


def test_validate_message_accepts_matching_identity_case_insensitive():
    event = {
        "object": {"t": 20},
        "time": "t",
        "deviceInfo": {"devEui": "DEVA", "applicationId": "APP1"},
    }

    assert validate_message(_TOPIC, _raw(event), max_bytes=65536) is not None


def test_validate_message_rejects_nan(caplog):
    with caplog.at_level("WARNING"):
        assert (
            validate_message(
                _TOPIC,
                b'{"object": {"v": NaN}, "time": "t"}',
                max_bytes=65536,
            )
            is None
        )


def test_validate_message_rejects_infinity(caplog):
    with caplog.at_level("WARNING"):
        assert (
            validate_message(
                _TOPIC,
                b'{"object": {"v": Infinity}, "time": "t"}',
                max_bytes=65536,
            )
            is None
        )
