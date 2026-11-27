"""Topologia declarativa de jobs, por tipo.

Este módulo é puro: não importa Pika nem abre conexão. Ele descreve filas,
DLQs e routing keys; `linx_shared.jobs.broker` aplica a declaração no canal.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from linx_shared.jobs.constants import (
    JOB_TYPE_PROVISION_APPLICATION,
    PROVISIONING_DEAD,
    PROVISIONING_DLQ,
    PROVISIONING_QUEUE,
    PROVISIONING_REQUESTED,
)


@dataclass(frozen=True)
class JobTypeTopology:
    """Nomes de infraestrutura de um tipo de job."""

    job_type: str
    command_queue: str
    dead_letter_queue: str
    requested_routing_key: str
    dead_routing_key: str
    status_binding: str


def job_type_topology(
    job_type: str,
    command_queue: str | None = None,
) -> JobTypeTopology:
    """Deriva a topologia de um tipo.

    O tipo legado ``provisioning.application`` preserva os nomes já em uso.
    Tipos novos seguem ``linx.jobs.<tipo>`` / ``linx.jobs.<tipo>.dlq``.
    """
    cleaned = (job_type or "").strip()
    if not cleaned:
        raise ValueError("job_type não pode ser vazio")

    if cleaned == JOB_TYPE_PROVISION_APPLICATION:
        return JobTypeTopology(
            job_type=cleaned,
            command_queue=command_queue or PROVISIONING_QUEUE,
            dead_letter_queue=PROVISIONING_DLQ,
            requested_routing_key=PROVISIONING_REQUESTED,
            dead_routing_key=PROVISIONING_DEAD,
            status_binding=f"{cleaned}.#",
        )

    return JobTypeTopology(
        job_type=cleaned,
        command_queue=command_queue or f"linx.jobs.{cleaned}",
        dead_letter_queue=f"linx.jobs.{cleaned}.dlq",
        requested_routing_key=f"{cleaned}.requested",
        dead_routing_key=f"{cleaned}.dead",
        status_binding=f"{cleaned}.#",
    )


JOB_TYPE_TOPOLOGIES: tuple[JobTypeTopology, ...] = (
    job_type_topology(JOB_TYPE_PROVISION_APPLICATION),
)


def topologies_for(job_types: Sequence[str]) -> tuple[JobTypeTopology, ...]:
    """Converte tipos em topologias, rejeitando lista vazia e duplicatas."""
    if not job_types:
        raise ValueError("informe ao menos um job_type")

    seen: set[str] = set()
    topologies: list[JobTypeTopology] = []
    for job_type in job_types:
        topology = job_type_topology(job_type)
        if topology.job_type in seen:
            raise ValueError(f"job_type duplicado: {topology.job_type}")
        seen.add(topology.job_type)
        topologies.append(topology)
    return tuple(topologies)
