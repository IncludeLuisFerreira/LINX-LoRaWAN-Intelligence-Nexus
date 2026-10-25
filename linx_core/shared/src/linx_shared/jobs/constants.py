from enum import StrEnum


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


JOB_TYPE_PROVISION_APPLICATION = "provisioning.application"

JOB_EXCHANGE = "linx.jobs"
JOB_DLX = "linx.jobs.dlx"
JOB_EVENTS_EXCHANGE = "linx.jobs.events"

PROVISIONING_QUEUE = "linx.jobs.provisioning"
PROVISIONING_DLQ = "linx.jobs.provisioning.dlq"
PROVISIONING_STATUS_QUEUE = "linx.jobs.status"

PROVISIONING_REQUESTED = "provisioning.application.requested"
PROVISIONING_STARTED = "provisioning.application.started"
PROVISIONING_SUCCEEDED = "provisioning.application.succeeded"
PROVISIONING_FAILED = "provisioning.application.failed"
PROVISIONING_RETRY = "provisioning.application.retry"
PROVISIONING_DEAD = "provisioning.application.dead"

RETRY_DELAYS_SECONDS = (5, 30, 120)
