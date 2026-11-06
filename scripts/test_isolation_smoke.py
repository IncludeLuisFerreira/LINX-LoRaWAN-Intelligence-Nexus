"""Unit minimo para as funcoes puras de scripts/test_isolation.py.

Roda sem nenhuma dependencia extra:
    python3 scripts/test_isolation_smoke.py
"""

import importlib.util
import sys
from pathlib import Path

SPEC_PATH = Path(__file__).resolve().parent / "test_isolation.py"
spec = importlib.util.spec_from_file_location("test_isolation", SPEC_PATH)
assert spec is not None and spec.loader is not None
iso = importlib.util.module_from_spec(spec)
# Registrar antes de exec_module: dataclasses em 3.13+ resolvem o modulo do
# cls via sys.modules durante @dataclass; sem isto, o import via importlib
# falha com AttributeError em NoneType.
sys.modules["test_isolation"] = iso
spec.loader.exec_module(iso)


def test_read_isolation_clean() -> None:
    rows_a = [{"app_id": "A", "payload": {"marker": iso.MARKER_A}}]
    rows_b = [{"app_id": "B", "payload": {"marker": iso.MARKER_B}}]
    assert iso.check_read_isolation(rows_a, rows_b) == []


def test_read_isolation_detects_leak() -> None:
    rows_a = [
        {"app_id": "A", "payload": {"marker": iso.MARKER_A}},
        {"app_id": "A", "payload": {"marker": iso.MARKER_B}},
    ]
    rows_b = [{"app_id": "B", "payload": {"marker": iso.MARKER_B}}]
    assert any("VAZAMENTO" in f for f in iso.check_read_isolation(rows_a, rows_b))


def test_route_isolation() -> None:
    assert iso.check_route_isolation(404) is None
    assert iso.check_route_isolation(200) is not None


def test_broker_denial() -> None:
    assert (
        iso.check_broker_namespace_denied(RuntimeError("ACCESS_REFUSED"), False) is None
    )
    assert iso.check_broker_namespace_denied(None, True) is not None


def test_namespace_regex() -> None:
    regex = iso.tenant_namespace_regex("abc")
    assert iso.re.match(regex, "linx.telemetry.abc")
    assert iso.re.match(regex, "linx.telemetry.abc.dlq")
    assert iso.re.match(regex, "linx.telemetry.abcd") is None


def test_uplink_payload_shape() -> None:
    body = iso.uplink_payload(iso.MARKER_A, "app1", "dev1")
    assert {"time", "object", "deviceInfo"} <= set(body)
    assert body["object"]["marker"] == iso.MARKER_A


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"OK   {fn.__name__}")
    print(f"{len(tests)} testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
