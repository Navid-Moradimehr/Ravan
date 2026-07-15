"""15-minute world-model evidence campaign.

This is a local validation campaign, not a plant certification test. It sends
canonical telemetry to the normalized Kafka boundary, publishes operational
events and artifact references, uploads small real artifacts to MinIO, and
compiles the captured evidence into a manifest-v2 bundle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from confluent_kafka import Producer

from services.common.model_dataset import compile_trajectory_bundle


def _publish(producer: Producer, topic: str, key: str, payload: dict[str, Any], counters: dict[str, int]) -> None:
    producer.produce(topic, key=key.encode(), value=json.dumps(payload, separators=(",", ":")).encode(), callback=lambda error, _message: counters.__setitem__("failed", counters["failed"] + 1) if error else counters.__setitem__("acknowledged", counters["acknowledged"] + 1))
    counters["attempted"] += 1
    producer.poll(0)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _upload_artifact(client: Any, bucket: str, key: str, body: bytes) -> str:
    try:
        client.head_bucket(Bucket=bucket)
    except Exception:
        client.create_bucket(Bucket=bucket)
    client.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/octet-stream")
    return hashlib.sha256(body).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a world-model evidence soak")
    parser.add_argument("--seconds", type=int, default=900)
    parser.add_argument("--sites", type=int, default=3)
    parser.add_argument("--telemetry-rate", type=float, default=1.0, help="samples per channel per site per second")
    parser.add_argument("--brokers", default=os.getenv("WORLD_MODEL_BROKERS", "localhost:19092"))
    parser.add_argument("--minio-endpoint", default=os.getenv("WORLD_MODEL_MINIO_ENDPOINT", "http://localhost:19000"))
    parser.add_argument("--report-dir", default=".datastream/reports/world-model-soak")
    parser.add_argument("--skip-compose", action="store_true")
    args = parser.parse_args()
    if args.seconds <= 0 or args.sites <= 0 or args.telemetry_rate <= 0:
        raise SystemExit("seconds, sites, and telemetry-rate must be positive")

    root = Path(args.report_dir)
    root.mkdir(parents=True, exist_ok=True)
    observations = root / "observations.jsonl"
    actions = root / "actions.jsonl"
    outcomes = root / "outcomes.jsonl"
    artifacts = root / "artifacts.jsonl"
    for path in (observations, actions, outcomes, artifacts):
        path.unlink(missing_ok=True)

    if not args.skip_compose:
        subprocess.run([
            "docker", "compose", "-f", "docker/docker-compose.yml", "--profile", "extended", "--profile", "world-model",
            "up", "-d", "--build", "kafka", "timescaledb", "timescaledb-migrate", "minio", "minio-init", "api-service",
            "processor", "fanout", "flink-job", "taskmanager", "operational-fanout", "artifact-fanout", "dataset-worker",
        ], check=True)

    try:
        import boto3
        client = boto3.client("s3", endpoint_url=args.minio_endpoint, aws_access_key_id="minio", aws_secret_access_key="minio12345", region_name="us-east-1")
    except Exception as exc:
        raise SystemExit(f"MinIO client unavailable: {exc}") from exc

    counters = {"attempted": 0, "acknowledged": 0, "failed": 0}
    producer = Producer({"bootstrap.servers": args.brokers, "client.id": "world-model-soak", "enable.idempotence": True, "acks": "all"})
    sites = [f"world-site-{index + 1}" for index in range(args.sites)]
    channels = (("pump-01", "pressure", "bar"), ("pump-01", "temperature", "c"), ("pump-01", "vibration", "mm/s"))
    started = time.monotonic()
    next_sample = started
    sample_index = 0
    artifact_count = 0
    action_rows: list[dict[str, Any]] = []
    outcome_rows: list[dict[str, Any]] = []
    artifact_rows: list[dict[str, Any]] = []
    with observations.open("w", encoding="utf-8") as observation_file, actions.open("w", encoding="utf-8") as action_file, outcomes.open("w", encoding="utf-8") as outcome_file, artifacts.open("w", encoding="utf-8") as artifact_file:
        for site in sites:
            boundary = {"event_id": str(uuid.uuid4()), "event_type": "episode.started", "event_kind": "boundary", "source_id": "world-model-soak", "site_id": site, "entity_id": "pump-01", "occurred_at": _utc(), "schema_version": 1, "schema_ref": "industrial.boundary.v1", "payload": {"episode_id": f"{site}-episode-1", "boundary_type": "start", "reason": "soak-start"}}
            _publish(producer, "industrial.operational", site, boundary, counters)

        while time.monotonic() - started < args.seconds:
            now = time.monotonic()
            if now < next_sample:
                time.sleep(min(next_sample - now, 0.05))
                continue
            occurred_at = _utc()
            for site_index, site in enumerate(sites):
                for channel_index, (asset, tag, unit) in enumerate(channels):
                    value = round((4.0 + site_index + channel_index * 0.3 + ((sample_index + channel_index) % 10) * 0.02), 4)
                    event = {"event_id": str(uuid.uuid4()), "ts_source": occurred_at, "source_protocol": ("opcua", "mqtt", "modbus")[channel_index], "source_id": f"{site}/{asset}", "asset_id": asset, "tag": tag, "value": value, "quality": "good", "unit": unit, "site": site, "line": "line-01", "schema_version": 1, "event_stage": "normalized", "context_id": f"{site}-episode-1"}
                    observation_file.write(json.dumps(event) + "\n")
                    _publish(producer, "industrial.normalized", f"{site}/{asset}/{tag}", event, counters)
                if sample_index % 5 == 0:
                    action = {"event_id": str(uuid.uuid4()), "event_type": "pump.speed.applied", "event_kind": "action", "source_id": f"{site}/controller", "site_id": site, "entity_id": "pump-01", "occurred_at": occurred_at, "schema_version": 1, "schema_ref": "industrial.action.v1", "payload": {"action_id": f"{site}-action-{sample_index}", "command": "speed", "requested_value": 20, "applied_value": 20, "unit": "%", "status": "applied", "effective_at": occurred_at, "control_mode": "simulated"}}
                    outcome = {"event_id": str(uuid.uuid4()), "event_type": "pump.yield.observed", "event_kind": "outcome", "source_id": f"{site}/quality", "site_id": site, "entity_id": "pump-01", "occurred_at": occurred_at, "schema_version": 1, "schema_ref": "industrial.outcome.v1", "payload": {"outcome_id": f"{site}-outcome-{sample_index}", "action_id": f"{site}-action-{sample_index}", "metric": "pressure_stability", "value": 0.96, "unit": "ratio", "success": True, "observed_at": occurred_at, "reward": 0.96}}
                    action_file.write(json.dumps({**action["payload"], "occurred_at": occurred_at, "site_id": site}) + "\n")
                    outcome_file.write(json.dumps({**outcome["payload"], "observed_at": occurred_at, "site_id": site}) + "\n")
                    action_rows.append(action); outcome_rows.append(outcome)
                    _publish(producer, "industrial.operational", f"{site}/action", action, counters)
                    _publish(producer, "industrial.operational", f"{site}/outcome", outcome, counters)
                if sample_index % 30 == 0:
                    body = f"simulated-thermal-frame site={site} sample={sample_index}\n".encode()
                    key = f"world-model-soak/{site}/artifact-{artifact_count}.bin"
                    digest = _upload_artifact(client, "lakehouse", key, body)
                    reference = {"artifact_id": f"{site}-artifact-{artifact_count}", "event_id": str(uuid.uuid4()), "site_id": site, "source_id": f"{site}/thermal-camera", "entity_id": "pump-01", "modality": "thermal", "uri": f"s3://lakehouse/{key}", "sha256": digest, "size_bytes": len(body), "content_type": "application/octet-stream", "encoding": "binary", "started_at": occurred_at, "ended_at": occurred_at, "clock_id": "world-model-soak-clock", "calibration_version": "cal-1", "topology_version": "topology-1", "schema_version": 1, "lineage_id": f"{site}-episode-1"}
                    artifact_file.write(json.dumps(reference) + "\n")
                    artifact_rows.append(reference)
                    _publish(producer, "industrial.observation-artifacts", f"{site}/artifact", reference, counters)
                    artifact_count += 1
            sample_index += 1
            next_sample += 1.0 / args.telemetry_rate
        for site in sites:
            boundary = {"event_id": str(uuid.uuid4()), "event_type": "episode.ended", "event_kind": "boundary", "source_id": "world-model-soak", "site_id": site, "entity_id": "pump-01", "occurred_at": _utc(), "schema_version": 1, "schema_ref": "industrial.boundary.v1", "payload": {"episode_id": f"{site}-episode-1", "boundary_type": "end", "reason": "soak-complete", "step": sample_index}}
            _publish(producer, "industrial.operational", site, boundary, counters)
    producer.flush(30)

    manifest = {"manifest_version": 2, "dataset_id": f"world-model-soak-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}", "site_ids": sites, "time_range": {}, "purpose": "dreamer", "observation_sources": str(observations), "action_sources": str(actions), "outcome_sources": str(outcomes), "artifact_sources": str(artifacts), "episode_definition": {"boundary": "industrial.boundary.v1"}, "alignment": {"sample_interval_ms": 1000, "max_skew_ms": 600}, "provenance": {"source": "world-model-soak", "protocols": ["opcua", "mqtt", "modbus"]}, "semantic_context": {"topology_version": "topology-1", "sites": sites}}
    manifest_path = root / "manifest.yaml"
    import yaml
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    bundle_result = compile_trajectory_bundle(manifest_path, root / "bundle")
    report = {"duration_seconds": round(time.monotonic() - started, 3), "configured_sites": sites, "sample_count": sample_index, "telemetry_records": sample_index * len(sites) * len(channels), "operational_records": len(action_rows) + len(outcome_rows) + len(sites) * 2, "artifact_records": len(artifact_rows), "kafka": counters, "bundle": bundle_result, "passed": counters["failed"] == 0 and bundle_result["valid"] and sample_index >= max(1, args.seconds - 2)}
    (root / "world-model-soak.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
