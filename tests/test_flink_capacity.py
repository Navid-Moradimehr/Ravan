from services.common.flink_capacity import decide_scaling, plan_capacity


def test_capacity_plan_is_bounded_by_partitions_and_host():
    plan = plan_capacity(
        topic="industrial.normalized",
        partitions=18,
        host_cpu=8,
        host_memory_mb=8192,
        max_parallelism=36,
        slots_per_taskmanager=1,
        events_per_second=5000,
        events_per_second_per_slot=500,
    )
    assert plan.parallelism == 7
    assert plan.taskmanager_replicas == 7
    assert plan.total_slots == 7
    assert plan.capacity_limited


def test_capacity_plan_can_follow_partitions_when_resources_allow():
    plan = plan_capacity(
        topic="industrial.normalized",
        partitions=18,
        host_cpu=24,
        host_memory_mb=32768,
        max_parallelism=18,
        slots_per_taskmanager=1,
    )
    assert plan.parallelism == 18


def test_scaling_decision_uses_lag_and_busy_time_hysteresis():
    assert decide_scaling(current_parallelism=2, min_parallelism=1, max_parallelism=18, partitions=18, lag=2000, busy_time=.9).action == "scale_up"
    assert decide_scaling(current_parallelism=2, min_parallelism=1, max_parallelism=18, partitions=18, lag=0, busy_time=.1).action == "scale_down"
    assert decide_scaling(current_parallelism=2, min_parallelism=1, max_parallelism=18, partitions=18, lag=100, busy_time=.5).action == "hold"
