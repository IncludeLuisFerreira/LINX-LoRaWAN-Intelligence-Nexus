import pytest

from linx_shared.jobs.constants import (
    JOB_TYPE_PROVISION_APPLICATION,
    PROVISIONING_DEAD,
    PROVISIONING_DLQ,
    PROVISIONING_QUEUE,
    PROVISIONING_REQUESTED,
)
from linx_shared.messaging.topology import (
    JOB_TYPE_TOPOLOGIES,
    job_type_topology,
    topologies_for,
)


def test_legacy_job_type_keeps_existing_names():
    topology = job_type_topology(JOB_TYPE_PROVISION_APPLICATION)

    assert topology.job_type == "provisioning.application"
    assert topology.command_queue == PROVISIONING_QUEUE
    assert topology.dead_letter_queue == PROVISIONING_DLQ
    assert topology.requested_routing_key == PROVISIONING_REQUESTED
    assert topology.dead_routing_key == PROVISIONING_DEAD
    assert topology.status_binding == "provisioning.application.#"


def test_legacy_job_type_accepts_command_queue_override():
    topology = job_type_topology(
        JOB_TYPE_PROVISION_APPLICATION,
        command_queue="linx.jobs.custom",
    )

    assert topology.command_queue == "linx.jobs.custom"
    assert topology.dead_letter_queue == PROVISIONING_DLQ


def test_new_job_type_derives_queue_dlq_and_bindings():
    topology = job_type_topology("provisioning.tenant")

    assert topology.command_queue == "linx.jobs.provisioning.tenant"
    assert topology.dead_letter_queue == "linx.jobs.provisioning.tenant.dlq"
    assert topology.requested_routing_key == "provisioning.tenant.requested"
    assert topology.dead_routing_key == "provisioning.tenant.dead"
    assert topology.status_binding == "provisioning.tenant.#"


def test_default_registry_contains_only_legacy_type():
    assert tuple(item.job_type for item in JOB_TYPE_TOPOLOGIES) == (
        JOB_TYPE_PROVISION_APPLICATION,
    )


def test_topologies_for_rejects_empty_sequence():
    with pytest.raises(ValueError, match="ao menos um"):
        topologies_for([])


def test_topologies_for_rejects_duplicate_types():
    with pytest.raises(ValueError, match="duplicado"):
        topologies_for(
            [JOB_TYPE_PROVISION_APPLICATION, JOB_TYPE_PROVISION_APPLICATION]
        )


def test_topologies_for_rejects_blank_type():
    with pytest.raises(ValueError, match="vazio"):
        topologies_for(["   "])


def test_topologies_for_returns_one_topology_per_type():
    topologies = topologies_for(
        [JOB_TYPE_PROVISION_APPLICATION, "provisioning.tenant"]
    )

    assert [item.job_type for item in topologies] == [
        "provisioning.application",
        "provisioning.tenant",
    ]
