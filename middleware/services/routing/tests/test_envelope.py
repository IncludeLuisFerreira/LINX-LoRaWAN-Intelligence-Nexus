from uuid import UUID

from routing.envelope import build_envelope, routing_key
from routing.validation import ValidUplink


def _uplink(event):
    return ValidUplink(
        app_id="app1", dev_eui="devA", event_type="up", event=event
    )


def test_build_envelope_has_uuid4_id():
    envelope = build_envelope(_uplink({"object": {}, "time": "t"}))

    parsed = UUID(envelope["envelope_id"])

    assert parsed.version == 4
    assert envelope["envelope_id"] == str(parsed)


def test_routing_key_format():
    assert (
        routing_key("app1", "devA", "up") == "application.app1.device.devA.up"
    )


def test_build_envelope_with_radio():
    event = {
        "object": {"t": 20},
        "rxInfo": [{"rssi": -60, "snr": 7.5}],
        "time": "2026-10-08T12:00:00Z",
    }

    envelope = build_envelope(_uplink(event))

    assert envelope["app_id"] == "app1"
    assert envelope["dev_eui"] == "devA"
    assert envelope["event_type"] == "up"
    assert envelope["payload"] == {"t": 20}
    assert envelope["rssi"] == -60
    assert envelope["snr"] == 7.5
    assert envelope["timestamp"] == "2026-10-08T12:00:00Z"
    assert UUID(envelope["envelope_id"]).version == 4


def test_build_envelope_without_rssi_snr_omits_keys():
    event = {"object": {}, "time": "t"}

    envelope = build_envelope(_uplink(event))

    assert envelope["payload"] == {}
    assert "rssi" not in envelope
    assert "snr" not in envelope


def test_build_envelope_empty_rxinfo_omits_keys():
    event = {"object": {}, "time": "t", "rxInfo": []}

    envelope = build_envelope(_uplink(event))

    assert "rssi" not in envelope
    assert "snr" not in envelope


def test_build_envelope_partial_rxinfo_only_rssi():
    event = {"object": {}, "time": "t", "rxInfo": [{"rssi": -70}]}

    envelope = build_envelope(_uplink(event))

    assert envelope["rssi"] == -70
    assert "snr" not in envelope
