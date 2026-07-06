from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable

try:  # pragma: no cover - exercised in the Flink container, not the lightweight repo env
    from pyflink.common import WatermarkStrategy
    from pyflink.common.configuration import Configuration
    from pyflink.common.serialization import SimpleStringSchema
    from pyflink.common.typeinfo import Types
    from pyflink.datastream import StreamExecutionEnvironment
    from pyflink.datastream.connectors.kafka import KafkaOffsetsInitializer, KafkaRecordSerializationSchema, KafkaSink, KafkaSource
    from pyflink.datastream.connectors.base import DeliveryGuarantee
    from pyflink.datastream.functions import KeyedProcessFunction
    from pyflink.datastream.state import ListStateDescriptor, ValueStateDescriptor
    from pyflink.datastream.functions import SinkFunction

    PYFLINK_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - repo/test environments without Flink packages
    WatermarkStrategy = None  # type: ignore[assignment]
    Configuration = None  # type: ignore[assignment]
    SimpleStringSchema = None  # type: ignore[assignment]
    Types = None  # type: ignore[assignment]
    StreamExecutionEnvironment = None  # type: ignore[assignment]
    KafkaOffsetsInitializer = None  # type: ignore[assignment]
    KafkaRecordSerializationSchema = None  # type: ignore[assignment]
    KafkaSink = None  # type: ignore[assignment]
    KafkaSource = None  # type: ignore[assignment]
    DeliveryGuarantee = None  # type: ignore[assignment]
    ListStateDescriptor = None  # type: ignore[assignment]
    ValueStateDescriptor = None  # type: ignore[assignment]
    SinkFunction = None  # type: ignore[assignment]

    class KeyedProcessFunction:  # type: ignore[no-redef]
        pass

    class SinkFunction:  # type: ignore[no-redef]
        pass

    PYFLINK_AVAILABLE = False

from services.common.brokers import resolve_kafka_brokers

from services.common.runtime_event import RuntimeEventRecord
from services.common.stream_scope import stream_partition_key
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
            ListStateDescriptor("industrial_window_samples", Types.TUPLE([Types.FLOAT(), Types.FLOAT()]))
        )
        self._temperature_sum_state = runtime_context.get_state(
            ValueStateDescriptor("industrial_temperature_sum", Types.FLOAT())
        )
        self._vibration_sum_state = runtime_context.get_state(
            ValueStateDescriptor("industrial_vibration_sum", Types.FLOAT())
        )

    def process_element(self, value: str, ctx) -> Iterable[str]:  # type: ignore[override]
        try:
            event = RuntimeEventRecord.from_raw_mapping(json.loads(value))
        except Exception:
            return []

        samples = list(self._sample_state.get() or [])
        temperature_sum = float(self._temperature_sum_state.value() or 0.0)
        vibration_sum = float(self._vibration_sum_state.value() or 0.0)

        current_sample = (event.temperature_c, event.vibration_mm_s)
        samples.append(current_sample)
        temperature_sum += event.temperature_c
        vibration_sum += event.vibration_mm_s

        evicted = False
        if len(samples) > self.window_limit:
            evicted_sample = samples.pop(0)
            temperature_str, vibration_str = evicted_sample
            temperature_sum -= float(temperature_str)
            vibration_sum -= float(vibration_str)
            evicted = True

        # Flink ListState has no single update(); only rewrite the list when an
        # eviction changed it. Otherwise appending the new sample is enough.
        if evicted:
            self._sample_state.clear()
            for sample in samples:
                self._sample_state.add(sample)
        else:
            self._sample_state.add(current_sample)

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



class ProcessedEventsSink(SinkFunction):
    """Persist processed events to the historian for Flink/Python parity.

    The Python runtime processor writes processed_events to the historian
    directly. The Flink job previously only wrote to the ``iot.processed``
    Kafka topic, so Flink-mode deployments lost historian persistence. This
    sink batches processed payloads and writes them through the shared
    historian client, restoring parity. It only activates when
    ``FLINK_PERSIST_PROCESSED_EVENTS=1`` (the historian client is only
    importable inside the Flink container).
    """

    def __init__(self, batch_size: int = 512) -> None:
        self._batch_size = batch_size
        self._buffer: list[dict] = []
        self._insert_batch = None
        self._insert_single = None

    def _ensure_client(self) -> None:
        if self._insert_batch is not None:
            return
        from services.historian.client import insert_processed_event, insert_processed_events

        self._insert_batch = insert_processed_events
        self._insert_single = insert_processed_event

    def invoke(self, value: str, context: object = None) -> None:  # type: ignore[override]
        try:
            payload = json.loads(value)
        except json.JSONDecodeError:
            return
        self._buffer.append(payload)
        if len(self._buffer) >= self._batch_size:
            self.flush()

    def flush(self) -> None:
        if not self._buffer:
            return
        self._ensure_client()
        batch = self._buffer[:]
        self._buffer.clear()
        try:
            self._insert_batch(batch)
        except Exception:
            for event in batch:
                try:
                    self._insert_single(event)
                except Exception:
                    pass


def _partition_key(raw: str) -> str:
    """Composite partition key matching the platform-wide stream scope.

    Uses the same 7-field key (project|site|line|protocol|source|asset|tag) as
    the edge publisher so the Flink key-by aligns with Kafka partitioning and
    keeps all samples for one asset+tag co-located in one task manager.
    """
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return "unknown"
    return stream_partition_key(payload).decode("utf-8")


def main() -> None:
    if not PYFLINK_AVAILABLE:
        raise RuntimeError("pyflink is required to run the distributed runtime job")

    brokers = resolve_kafka_brokers("localhost:19092")
    input_topic = os.getenv("IOT_TOPIC", os.getenv("INDUSTRIAL_NORMALIZED_TOPIC", "industrial.normalized"))
    output_topic = os.getenv("PROCESSED_TOPIC", "iot.processed")
    window_limit = max(1, int(os.getenv("RUNTIME_WINDOW_LIMIT", "25")))
    parallelism = int(os.getenv("FLINK_PARALLELISM", "4"))
    checkpoint_interval_ms = int(os.getenv("FLINK_CHECKPOINT_INTERVAL_MS", "10000"))
    starting_offsets = os.getenv("FLINK_STARTING_OFFSETS", "latest").strip().lower()

    connector_jars = [
        os.getenv("FLINK_KAFKA_CONNECTOR_JAR", "file:///opt/flink/lib/flink-connector-kafka-3.3.0-1.20.jar"),
        os.getenv("FLINK_KAFKA_CLIENTS_JAR", "file:///opt/flink/lib/kafka-clients-3.8.1.jar"),
    ]
    existing_jars = []
    for jar_uri in connector_jars:
        if jar_uri.startswith("file://"):
            local_path = Path(jar_uri.removeprefix("file://"))
            if local_path.exists():
                existing_jars.append(jar_uri)
        else:
            existing_jars.append(jar_uri)

    configuration = Configuration()
    if existing_jars:
        configuration.set_string("pipeline.jars", ";".join(existing_jars))

    env = StreamExecutionEnvironment.get_execution_environment(configuration)
    env.set_parallelism(parallelism)
    if checkpoint_interval_ms > 0:
        env.enable_checkpointing(checkpoint_interval_ms)

    source = (
        KafkaSource.builder()
        .set_bootstrap_servers(brokers)
        .set_topics(input_topic)
        .set_group_id("iot-anomaly-processor")
        .set_starting_offsets(
            KafkaOffsetsInitializer.earliest() if starting_offsets == "earliest" else KafkaOffsetsInitializer.latest()
        )
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
        .set_delivery_guarantee(DeliveryGuarantee.AT_LEAST_ONCE)
        .set_property("batch.size", "16384")
        .set_property("linger.ms", "10")
        .set_property("compression.type", "lz4")
        .build()
    )

    stream = env.from_source(source, WatermarkStrategy.no_watermarks(), "kafka-iot-source")
    keyed = stream.key_by(_partition_key)
    processed = keyed.process(IndustrialRuntimeProcessFunction(window_limit), output_type=Types.STRING())
    processed.sink_to(sink)

    # Optionally persist processed events to the historian for Flink/Python
    # parity. The historian client is only importable inside the Flink container.
    if os.getenv("FLINK_PERSIST_PROCESSED_EVENTS", "").strip().lower() in {"1", "true", "yes"}:
        processed.add_sink(ProcessedEventsSink(batch_size=int(os.getenv("FLINK_PROCESSED_BATCH_SIZE", "512"))))

    env.execute("iot-anomaly-processor")


if __name__ == "__main__":
    main()
