"""Bounded Flink/Kafka capacity planning primitives.

The planner is intentionally deterministic. It recommends deployment capacity;
it does not mutate a running cluster. Kubernetes runtime changes are delegated
to the Flink Kubernetes Operator, while Compose uses the result at startup.
"""

from __future__ import annotations

import math
import os
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class CapacityPlan:
    topic: str
    partitions: int
    host_cpu: int
    host_memory_mb: int
    min_parallelism: int
    max_parallelism: int
    parallelism: int
    slots_per_taskmanager: int
    taskmanager_replicas: int
    total_slots: int
    estimated_events_per_second: float | None
    estimated_capacity_events_per_second: float
    capacity_limited: bool
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ScalingDecision:
    action: str
    target_parallelism: int
    reason: str


def _positive(value: int | float, fallback: int | float) -> int | float:
    return value if value > 0 else fallback


def plan_capacity(
    *,
    topic: str,
    partitions: int,
    host_cpu: int | None = None,
    host_memory_mb: int | None = None,
    min_parallelism: int = 1,
    max_parallelism: int | None = None,
    slots_per_taskmanager: int = 1,
    reserved_cpu: int = 1,
    reserved_memory_mb: int = 1024,
    memory_per_slot_mb: int = 1024,
    events_per_second: float | None = None,
    events_per_second_per_slot: float = 250.0,
) -> CapacityPlan:
    """Calculate bounded startup capacity from partitions and host resources."""
    partitions = max(1, int(partitions))
    host_cpu = max(1, int(host_cpu or (os.cpu_count() or 1)))
    host_memory_mb = max(256, int(host_memory_mb or 4096))
    min_parallelism = max(1, int(min_parallelism))
    max_parallelism = max(min_parallelism, int(max_parallelism or partitions))
    slots_per_taskmanager = max(1, int(slots_per_taskmanager))
    available_cpu = max(1, host_cpu - max(0, int(reserved_cpu)))
    available_memory = max(memory_per_slot_mb, host_memory_mb - max(0, int(reserved_memory_mb)))
    resource_limit = min(available_cpu, available_memory // max(1, int(memory_per_slot_mb)))
    partition_limit = partitions
    throughput_target = None
    if events_per_second is not None:
        throughput_target = max(1, math.ceil(float(events_per_second) / max(1.0, float(events_per_second_per_slot))))

    # With no throughput estimate, cover the current source partitions. A
    # resource cap may still choose a lower safe value and emit a warning.
    requested = max(min_parallelism, throughput_target or partitions)
    parallelism = min(requested, max_parallelism, partition_limit, resource_limit)
    parallelism = max(1, parallelism)
    total_slots = int(math.ceil(parallelism / slots_per_taskmanager) * slots_per_taskmanager)
    replicas = max(1, math.ceil(total_slots / slots_per_taskmanager))
    estimated_capacity = parallelism * max(1.0, float(events_per_second_per_slot))
    warnings: list[str] = []
    if max_parallelism > partitions:
        warnings.append("max_parallelism exceeds current Kafka partitions; source parallelism cannot use the extra capacity until partitions increase")
    if requested > parallelism:
        warnings.append("requested capacity is limited by partitions or available host resources")
    if partitions & (partitions - 1):
        warnings.append("partition count is not a power of two; choose a max parallelism with useful divisors for future rescaling")
    if slots_per_taskmanager > 1:
        warnings.append("multiple slots per TaskManager improve utilization but reduce task isolation")
    return CapacityPlan(
        topic=topic,
        partitions=partitions,
        host_cpu=host_cpu,
        host_memory_mb=host_memory_mb,
        min_parallelism=min_parallelism,
        max_parallelism=max_parallelism,
        parallelism=parallelism,
        slots_per_taskmanager=slots_per_taskmanager,
        taskmanager_replicas=replicas,
        total_slots=total_slots,
        estimated_events_per_second=events_per_second,
        estimated_capacity_events_per_second=round(estimated_capacity, 2),
        capacity_limited=requested > parallelism,
        warnings=tuple(warnings),
    )


def decide_scaling(
    *,
    current_parallelism: int,
    min_parallelism: int,
    max_parallelism: int,
    partitions: int,
    lag: float,
    busy_time: float,
    lag_scale_up: int = 1000,
    lag_scale_down: int = 10,
    busy_scale_up: float = 0.75,
    busy_scale_down: float = 0.30,
) -> ScalingDecision:
    """Return a bounded recommendation for an external autoscaler/operator."""
    current = max(1, int(current_parallelism))
    upper = max(current, min(int(max_parallelism), max(1, int(partitions))))
    lower = max(1, int(min_parallelism))
    if lag >= lag_scale_up and busy_time >= busy_scale_up and current < upper:
        return ScalingDecision("scale_up", min(current + 1, upper), "lag and busy time exceed scale-up thresholds")
    if lag <= lag_scale_down and busy_time <= busy_scale_down and current > lower:
        return ScalingDecision("scale_down", max(current - 1, lower), "lag and busy time are below scale-down thresholds")
    return ScalingDecision("hold", current, "capacity is within the configured hysteresis band")
