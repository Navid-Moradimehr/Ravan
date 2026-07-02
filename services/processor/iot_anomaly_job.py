from __future__ import annotations

import os

from pyflink.common import WatermarkStrategy
from pyflink.common.serialization import SimpleStringSchema
from pyflink.common.typeinfo import Types
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import KafkaOffsetsInitializer, KafkaRecordSerializationSchema, KafkaSink, KafkaSource

from services.processor.scoring import score_event, severity_for


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

    from services.common.runtime_event import RuntimeEventRecord

    event = RuntimeEventRecord.from_raw_mapping(json.loads(raw))
    temperature = float(event.temperature_c)
    vibration = float(event.vibration_mm_s)
    anomaly_score = score_event(
        event,
        temperature_avg=temperature,
        vibration_avg=vibration,
        detector=None,
    )

    event.mark_processed(
        window_size=1,
        temperature_avg_c=round(temperature, 2),
        vibration_avg_mm_s=round(vibration, 2),
        anomaly_score=anomaly_score,
        severity=severity_for(anomaly_score),
    )
    return json.dumps(event.to_dict(), separators=(",", ":"))


if __name__ == "__main__":
    main()
