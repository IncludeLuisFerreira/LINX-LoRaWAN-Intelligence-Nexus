import pytest
from linx_shared.jobs.consumer import InvalidMessageError

from jobs_worker.main import _parse_envelope, _parse_status_event


@pytest.mark.parametrize(
    "payload",
    [
        b"{not-json",
        b'{"job_id": "00000000-0000-0000-0000-000000000000"}',
    ],
)
def test_malformed_job_envelope_is_invalid_message(payload):
    with pytest.raises(InvalidMessageError):
        _parse_envelope(payload)


def test_malformed_status_event_is_invalid_message():
    with pytest.raises(InvalidMessageError):
        _parse_status_event(b'{"job_id": "not-a-uuid"}')
