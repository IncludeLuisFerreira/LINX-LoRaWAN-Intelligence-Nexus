from uuid import UUID, uuid4

from linx_shared.grpc import linx_agent_pb2

TelemetryEvent = getattr(linx_agent_pb2, "TelemetryEvent")
Violation = getattr(linx_agent_pb2, "Violation")


def test_telemetry_event_round_trip_preserves_event_id() -> None:
    event_id = str(uuid4())
    event = TelemetryEvent(dev_eui="dev", event_id=event_id)

    assert event.event_id == event_id
    assert UUID(event.event_id).version == 4

    parsed = TelemetryEvent.FromString(event.SerializeToString())
    assert parsed.dev_eui == "dev"
    assert parsed.event_id == event_id
    assert UUID(parsed.event_id).version == 4


def test_violation_round_trip_preserves_violation_id() -> None:
    violation_id = str(uuid4())
    violation = Violation(violation_id=violation_id)

    assert violation.violation_id == violation_id
    assert UUID(violation.violation_id).version == 4

    parsed = Violation.FromString(violation.SerializeToString())
    assert parsed.violation_id == violation_id
    assert UUID(parsed.violation_id).version == 4
