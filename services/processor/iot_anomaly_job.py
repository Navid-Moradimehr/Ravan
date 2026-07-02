from __future__ import annotations

import json
import os
from typing import Iterable

try:  # pragma: no cover - exercised in the Flink container, not the lightweight repo env
    from pyflink.common import WatermarkStrategy
    from pyflink.common.serialization import SimpleStringSchema
    from pyflink.common.typeinfo import Types
    from pyflink.datastream import StreamExecutionEnvironment
    from pyflink.datastream.connectors.kafka import KafkaOffsetsInitializer, KafkaRecordSerializationSchema, KafkaSink, KafkaSource
    from pyflink.datastream.functions import KeyedProcessFunction
    from pyflink.datastream.state import ListStateDescriptor, ValueStateDescriptor

    PYFLINK_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - repo/test environments without Flink packages
    WatermarkStrategy = None  # type: ignore[assignment]
    SimpleStringSchema = None  # type: ignore[assignment]
    Types = None  # type: ignore[assignment]
    StreamExecutionEnvironment = None  # type: ignore[assignment]
    KafkaOffsetsInitializer = None  # type: ignore[assignment]
    KafkaRecordSerializationSchema = None  # type: ignore[assignment]
    KafkaSink = None  # type: ignore[assignment]
    KafkaSource = None  # type: ignore[assignment]
    ListStateDescriptor = None  # type: ignore[assignment]
    ValueStateDescriptor = None  # type: ignore[assignment]

    class KeyedProcessFunction:  # type: ignore[no-redef]
        pass

    PYFLINK_AVAILABLE = False

from services.common.runtime_event import RuntimeEventRecord
from services.processor.runtime_pipeline import build_runtime_event_payload


class IndustrialRuntimeProcessFunction(KeyedProcessFunction):
    """Stateful keyed windowing for the distributed runtime path.

    The Python fallback processor keeps its own in-memory deque per device.
    This Flink job mirrors the same enrichment contract but stores the rolling
    samples in keyed state so the stream can be scaled horizontally across task
    managers without changing the output contract.
    """

    def __init__(self, window_limit: int) -> None:
        self.window_limit = max(1, window_limit)
        self._sample_state = None
        self._temperature_sum_state = None
        self._vibration_sum_state = None

    def open(self, runtime_context) -> None:  # type: ignore[override]
        self._sample_state = runtime_context.get_list_state(
            ListStateDescriptor("industrial_window_samples", Types.STRING())
        )
        self._temperature_sum_state = runtime_context.get_state(
            ValueStateDescriptor("industrial_temperature_sum", Types.FLOAT())
        )
        self._vibration_sum_state = runtime_context.get_state(
            ValueStateDescriptor("industrial_vibration_sum", Types.FLOAT())
        )

    def process_element(self, value: str, ctx) -> Iterable[str]:  # type: ignore[override]
        event = RuntimeEventRecord.from_raw_mapping(json.loads(value))

        samples = list(self._sample_state.get() or [])
        temperature_sum = float(self._temperature_sum_state.value() or 0.0)
        vibration_sum = float(self._vibration_sum_state.value() or 0.0)

        current_sample = f"{event.temperature_c}:{event.vibration_mm_s}"
        samples.append(current_sample)
        temperature_sum += event.temperature_c
        vibration_sum += event.vibration_mm_s

        if len(samples) > self.window_limit:
            evicted = samples.pop(0)
            temperature_str, vibration_str = evicted.split(":", 1)
            temperature_sum -= float(temperature_str)
            vibration_sum -= float(vibration_str)

        self._sample_state.clear()
        for sample in samples:
            self._sample_state.add(sample)

        self._temperature_sum_state.update(temperature_sum)
        self._vibration_sum_state.update(vibration_sum)

        window_size = len(samples)
        temperature_avg = temperature_sum / window_size if window_size else 0.0
        vibration_avg = vibration_sum / window_size if window_size else 0.0
        payload = build_runtime_event_payload(
            event,
            temperature_avg_c=temperature_avg,
            vibration_avg_mm_s=vibration_avg,
            window_size=window_size,
        )
        yield json.dumps(payload, separators=(",", ":"))


def _partition_key(raw: str) -> str:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return "unknown"
    return str(payload.get("asset_id") or payload.get("device_id") or "unknown")


def main() -> None:
    if not PYFLINK_AVAILABLE:
        raise RuntimeError("pyflink is required to run the distributed runtime job")

    brokers = os.getenv("REDPANDA_BROKERS", "redpanda:9092")
    input_topic = os.getenv("IOT_TOPIC", "iot.raw")
    output_topic = os.getenv("PROCESSED_TOPIC", "iot.processed")
    window_limit = max(1, int(os.getenv("RUNTIME_WINDOW_LIMIT", "25")))
    parallelism = int(os.getenv("FLINK_PARALLELISM", "4"))
    checkpoint_interval_ms = int(os.getenv("FLINK_CHECKPOINT_INTERVAL_MS", "10000"))

    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(parallelism)
    if checkpoint_interval_ms > 0:
        env.enable_checkpointing(checkpoint_interval_ms)

    source = (
        KafkaSource.builder()
        .set_bootstrap_servers(brokers)
        .set_topics(input_topic)
        .set_group_id("iot-anomaly-processor")
        .set_starting_offsets(KafkaOffsetsInitializer.latest())
        .set_value_only_deserializer(SimpleStringSchema())
        .set_property("fetch.min.bytes", "1048576")
        .set_property("fetch.max.wait.ms", "500")
        .build()
    )

    sink = (
        KafkaSink.builder()
        .set_bootstrap_servers(brokers)
        .set_record_serializer(
            KafkaRecordSerializationSchema.builder()
            .set_topic(output_topic)
            .set_value_serialization_schema(SimpleStringSchema())
            .build()
        )
        .set_delivery_guarantee("at_least_once")
        .set_property("batch.size", "16384")
        .set_property("linger.ms", "10")
        .set_property("compression.type", "lz4")
        .build()
    )

    stream = env.from_source(source, WatermarkStrategy.no_watermarks(), "redpanda-iot-source")
    keyed = stream.key_by(_partition_key)
    processed = keyed.process(IndustrialRuntimeProcessFunction(window_limit), output_type=Types.STRING())
    processed.sink_to(sink)

    env.execute("iot-anomaly-processor")


if __name__ == "__main__":
    main()
