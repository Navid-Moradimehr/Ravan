from __future__ import annotations

import os

from pyflink.common import WatermarkStrategy
from pyflink.common.serialization import SimpleStringSchema
from pyflink.common.typeinfo import Types
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import KafkaOffsetsInitializer, KafkaRecordSerializationSchema, KafkaSink, KafkaSource


def main() -> None:
    brokers = os.getenv("REDPANDA_BROKERS", "redpanda:9092")
    input_topic = os.getenv("IOT_TOPIC", "iot.raw")
    output_topic = os.getenv("PROCESSED_TOPIC", "iot.processed")

    env = StreamExecutionEnvironment.get_execution_environment()
    # Parallelism: auto-detect from environment or default to 4
parallelism = int(os.getenv("FLINK_PARALLELISM", "4"))
env.set_parallelism(parallelism)

    source = (
        KafkaSource.builder()
        .set_bootstrap_servers(brokers)
        .set_topics(input_topic)
        .set_group_id("iot-anomaly-processor")
        .set_starting_offsets(KafkaOffsetsInitializer.latest())
        .set_value_only_deserializer(SimpleStringSchema())
        .set_property("fetch.min.bytes", "1048576")  # 1MB batch fetch
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
    processed = stream.map(
        lambda raw: enrich_event(raw),
        output_type=Types.STRING(),
    )
    processed.sink_to(sink)

    env.execute("iot-anomaly-processor")


def enrich_event(raw: str) -> str:
    import json
    from datetime import datetime, timezone

    event = json.loads(raw)
    temperature = float(event.get("temperature_c", 0))
    vibration = float(event.get("vibration_mm_s", 0))
    pressure = float(event.get("pressure_bar", 0))
    anomaly_score = 0

    if temperature >= 65:
        anomaly_score += 0.4
    if vibration >= 7:
        anomaly_score += 0.4
    if pressure >= 8:
        anomaly_score += 0.2

    event["processed_at"] = datetime.now(timezone.utc).isoformat()
    event["anomaly_score"] = round(anomaly_score, 2)
    event["severity"] = "critical" if anomaly_score >= 0.8 else "warning" if anomaly_score >= 0.4 else "normal"
    return json.dumps(event, separators=(",", ":"))


if __name__ == "__main__":
    main()
