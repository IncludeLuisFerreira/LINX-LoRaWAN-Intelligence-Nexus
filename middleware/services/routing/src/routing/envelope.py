from typing import Any

from routing.validation import ValidUplink


def routing_key(app_id: str, dev_eui: str, event_type: str) -> str:
    return f"application.{app_id}.device.{dev_eui}.{event_type}"


def build_envelope(uplink: ValidUplink) -> dict[str, Any]:
    envelope: dict[str, Any] = {
        "app_id": uplink.app_id,
        "dev_eui": uplink.dev_eui,
        "event_type": uplink.event_type,
        "payload": uplink.event["object"],
        "timestamp": uplink.event["time"],
    }

    rx_info = uplink.event.get("rxInfo")
    if isinstance(rx_info, list) and rx_info:
        first = rx_info[0]
        if isinstance(first, dict):
            if "rssi" in first:
                envelope["rssi"] = first["rssi"]
            if "snr" in first:
                envelope["snr"] = first["snr"]

    return envelope
