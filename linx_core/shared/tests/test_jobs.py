from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from linx_shared.jobs.constants import (
    JOB_TYPE_PROVISION_APPLICATION,
    RETRY_DELAYS_SECONDS,
    JobStatus,
)
from linx_shared.jobs.envelope import JobEnvelope, JobStatusEvent
from linx_shared.models.job import Job
from linx_shared.models.job_outbox import JobOutbox


def test_retry_delays():
    assert RETRY_DELAYS_SECONDS == (5, 30, 120)


def test_job_defaults_and_columns():
    job = Job(
        type=JOB_TYPE_PROVISION_APPLICATION,
        tenant_id=uuid4(),
        subject_id=uuid4(),
        payload={"application_id": "x"},
        command_exchange="linx.jobs",
        command_routing_key="provisioning.application.requested",
        deduplication_key="provisioning.application:x",
    )
    assert job.status == JobStatus.PENDING.value
    assert job.attempts == 0
    assert job.max_attempts == 3
    assert job.result is None
    assert job.error is None
    assert job.command_routing_key == "provisioning.application.requested"


def test_job_outbox_defaults():
    outbox = JobOutbox(
        job_id=uuid4(),
        exchange="linx.jobs",
        routing_key="provisioning.application.requested",
        payload={"job_id": "x"},
    )
    assert outbox.published_at is None
    assert outbox.attempts == 0


def test_job_envelope_round_trip():
    raw = {
        "job_id": str(uuid4()),
        "type": JOB_TYPE_PROVISION_APPLICATION,
        "tenant_id": str(uuid4()),
        "subject_id": str(uuid4()),
        "payload": {"application_id": "x"},
        "attempt": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    envelope = JobEnvelope.model_validate(raw)
    assert envelope.model_dump(mode="json")["type"] == (
        JOB_TYPE_PROVISION_APPLICATION
    )


def test_job_envelope_rejects_missing_tenant():
    with pytest.raises(ValidationError):
        JobEnvelope.model_validate(
            {
                "job_id": str(uuid4()),
                "type": JOB_TYPE_PROVISION_APPLICATION,
                "subject_id": str(uuid4()),
                "payload": {},
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )


def test_status_event_supports_retry():
    event = JobStatusEvent(
        job_id=uuid4(),
        type=JOB_TYPE_PROVISION_APPLICATION,
        status=JobStatus.PENDING,
        attempt=1,
        next_attempt_at=datetime.now(timezone.utc),
    )
    assert event.status == JobStatus.PENDING
    assert event.next_attempt_at is not None
