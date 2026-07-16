"""15-minute world-model evidence campaign.

This is a local validation campaign, not a plant certification test. It sends
canonical telemetry to the normalized Kafka boundary, publishes operational
events and artifact references, uploads small real artifacts to MinIO, and
compiles the captured evidence into a manifest-v3 bundle and verifies the
bounded downstream records when the local stack is available.
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
from urllib.parse import urlparse
from urllib.request import urlopen

from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic

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


def _ensure_topics(brokers: str) -> None:
    admin = AdminClient({"bootstrap.servers": brokers})
    topics = ["industrial.normalized", "industrial.operational", "industrial.observation-artifacts"]
    futures = admin.create_topics([NewTopic(topic, num_partitions=3, replication_factor=1) for topic in topics])
    for topic, future in futures.items():
        try:
            future.result()
        except Exception as exc:
            if "already exists" not in str(exc).lower():
                raise RuntimeError(f"could not create Kafka topic {topic}: {exc}") from exc


def _verify_timescale(
    observation_ids: list[str],
    operational_ids: list[str],
) -> dict[str, Any]:
    """Verify exact campaign IDs without scanning the full historian."""

    try:
        import psycopg2

        connection = psycopg2.connect(
            os.getenv("WORLD_MODEL_DATABASE_URL", "postgresql://stream:stream@localhost:15432/stream_engine"),
            connect_timeout=5,
        )
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute("SET statement_timeout = 15000")

            def count(table: str, column: str, values: list[str]) -> int:
                if not values:
                    return 0
                cursor.execute(f"SELECT COUNT(DISTINCT {column}) FROM {table} WHERE {column} = ANY(%s)", (values,))
                return int(cursor.fetchone()[0])

            industrial = count("industrial_events", "event_id", observation_ids)
            processed = count("processed_events", "event_id", observation_ids)
        connection.close()
        return {
            "status": "passed" if industrial == len(observation_ids) and processed == len(observation_ids) else "failed",
            "industrial_events": {"expected": len(observation_ids), "matched": industrial},
            "processed_events": {"expected": len(observation_ids), "matched": processed},
            "operational_events": {"expected": len(operational_ids), "matched": None, "note": "operational events are verified in Iceberg"},
        }
    except Exception as exc:
        return {"status": "unavailable", "error": str(exc)}


def _iceberg_match_count(table: Any, column: str, values: list[str]) -> int:
    if not values:
        return 0
    from functools import reduce

    from pyiceberg.expressions import EqualTo, Or

    expression = reduce(lambda left, value: Or(left, EqualTo(column, value)), values[1:], EqualTo(column, values[0]))
    return int(table.scan(row_filter=expression).to_arrow().num_rows)


def _verify_lakehouse(
    operational_ids: list[str],
    artifact_ids: list[str],
) -> dict[str, Any]:
    """Use Iceberg predicate pushdown instead of a broad historical scan."""

    try:
        from pyiceberg.catalog import load_catalog

        catalog = load_catalog(
            os.getenv("LAKEHOUSE_CATALOG", "sql"),
            type=os.getenv("LAKEHOUSE_CATALOG", "sql"),
            warehouse=os.getenv("WORLD_MODEL_LAKEHOUSE_WAREHOUSE", "s3://lakehouse/"),
            uri=os.getenv("WORLD_MODEL_LAKEHOUSE_CATALOG_URI", "postgresql+psycopg2://stream:stream@localhost:15432/stream_engine"),
            **{
                "s3.endpoint": os.getenv("WORLD_MODEL_MINIO_ENDPOINT", "http://localhost:19000"),
                "s3.access-key-id": os.getenv("WORLD_MODEL_MINIO_ACCESS_KEY", "minio"),
                "s3.secret-access-key": os.getenv("WORLD_MODEL_MINIO_SECRET_KEY", "minio12345"),
                "s3.region": os.getenv("WORLD_MODEL_MINIO_REGION", "us-east-1"),
            },
        )
        operational_table = catalog.load_table(("industrial", os.getenv("LAKEHOUSE_OPERATIONAL_TABLE", "operational_events_v2")))
        artifact_table = catalog.load_table(("industrial", os.getenv("LAKEHOUSE_ARTIFACT_TABLE", "observation_artifacts")))
        operational_count = _iceberg_match_count(operational_table, "event_id", operational_ids)
        artifact_count = _iceberg_match_count(artifact_table, "artifact_id", artifact_ids)
        return {
            "status": "passed" if operational_count == len(operational_ids) and artifact_count == len(artifact_ids) else "failed",
            "operational_events": {"expected": len(operational_ids), "matched": operational_count},
            "artifacts": {"expected": len(artifact_ids), "matched": artifact_count},
        }
    except Exception as exc:
        return {"status": "unavailable", "error": str(exc)}


def _verify_minio(client: Any, artifact_rows: list[dict[str, Any]]) -> dict[str, Any]:
    checked = 0
    mismatches: list[str] = []
    try:
        for row in artifact_rows:
            parsed = urlparse(str(row["uri"]))
            body = client.get_object(Bucket=parsed.netloc, Key=parsed.path.lstrip("/"))["Body"].read()
            checked += 1
            if len(body) != int(row["size_bytes"]) or hashlib.sha256(body).hexdigest() != row["sha256"]:
                mismatches.append(str(row.get("artifact_id", "unknown")))
        return {"status": "passed" if checked == len(artifact_rows) and not mismatches else "failed", "expected": len(artifact_rows), "checked": checked, "mismatches": mismatches}
    except Exception as exc:
        return {"status": "unavailable", "checked": checked, "error": str(exc)}


def _verify_flink() -> dict[str, Any]:
    try:
        with urlopen(os.getenv("WORLD_MODEL_FLINK_URL", "http://localhost:18088/jobs/overview"), timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        jobs = payload.get("jobs", [])
        running = [job for job in jobs if str(job.get("state", "")).upper() == "RUNNING"]
        return {"status": "passed" if running else "failed", "jobs": jobs}
    except Exception as exc:
        return {"status": "unavailable", "error": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a world-model evidence soak")
    parser.add_argument("--seconds", type=int, default=900)
    parser.add_argument("--sites", type=int, default=3)
    parser.add_argument("--telemetry-rate", type=float, default=1.0, help="samples per channel per site per second")
    parser.add_argument("--brokers", default=os.getenv("WORLD_MODEL_BROKERS", "localhost:19092"))
    parser.add_argument("--minio-endpoint", default=os.getenv("WORLD_MODEL_MINIO_ENDPOINT", "http://localhost:19000"))
    parser.add_argument("--report-dir", default=".datastream/reports/world-model-soak")
    parser.add_argument("--campaign-id", default="", help="stable identifier for this campaign; generated when omitted")
    parser.add_argument("--skip-compose", action="store_true")
    parser.add_argument("--skip-downstream-verify", action="store_true", help="only skip explicit downstream checks when dependencies are intentionally unavailable")
    args = parser.parse_args()
    if args.seconds <= 0 or args.sites <= 0 or args.telemetry_rate <= 0:
        raise SystemExit("seconds, sites, and telemetry-rate must be positive")

    campaign_id = args.campaign_id.strip() or f"wm-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    root = Path(args.report_dir) / campaign_id
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
    _ensure_topics(args.brokers)
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
    observation_ids: list[str] = []
    operational_ids: list[str] = []
    episode_rows: list[dict[str, Any]] = []
    episode_ids = {site: f"{campaign_id}-{site}-episode-1" for site in sites}
    campaign_started_at = _utc()
    with observations.open("w", encoding="utf-8") as observation_file, actions.open("w", encoding="utf-8") as action_file, outcomes.open("w", encoding="utf-8") as outcome_file, artifacts.open("w", encoding="utf-8") as artifact_file:
        for site in sites:
            boundary_event_id = str(uuid.uuid4())
            boundary = {"event_id": boundary_event_id, "event_type": "episode.started", "event_kind": "boundary", "source_id": "world-model-soak", "site_id": site, "entity_id": "pump-01", "occurred_at": _utc(), "schema_version": 1, "schema_ref": "industrial.boundary.v1", "payload": {"campaign_id": campaign_id, "episode_id": episode_ids[site], "boundary_type": "start", "reason": "soak-start"}}
            operational_ids.append(boundary_event_id)
            episode_rows.append({"event_id": boundary_event_id, "site_id": site, "episode_id": episode_ids[site], "boundary_type": "start", "occurred_at": boundary["occurred_at"], "campaign_id": campaign_id})
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
                    event_id = str(uuid.uuid4())
                    event = {"event_id": event_id, "campaign_id": campaign_id, "ts_source": occurred_at, "source_protocol": ("opcua", "mqtt", "modbus")[channel_index], "source_id": f"{site}/{asset}", "asset_id": asset, "tag": tag, "value": value, "quality": "good", "unit": unit, "site": site, "site_id": site, "line": "line-01", "schema_version": 1, "event_stage": "normalized", "episode_id": episode_ids[site], "context_id": episode_ids[site]}
                    observation_ids.append(event_id)
                    observation_file.write(json.dumps(event) + "\n")
                    _publish(producer, "industrial.normalized", f"{site}/{asset}/{tag}", event, counters)
                if sample_index % 5 == 0:
                    action_id = f"{campaign_id}-{site}-action-{sample_index}"
                    outcome_id = f"{campaign_id}-{site}-outcome-{sample_index}"
                    action = {"event_id": str(uuid.uuid4()), "event_type": "pump.speed.applied", "event_kind": "action", "source_id": f"{site}/controller", "site_id": site, "entity_id": "pump-01", "occurred_at": occurred_at, "schema_version": 1, "schema_ref": "industrial.action.v1", "payload": {"campaign_id": campaign_id, "episode_id": episode_ids[site], "action_id": action_id, "command": "speed", "requested_value": 20, "applied_value": 20, "unit": "%", "status": "applied", "effective_at": occurred_at, "control_mode": "simulated"}}
                    outcome = {"event_id": str(uuid.uuid4()), "event_type": "pump.yield.observed", "event_kind": "outcome", "source_id": f"{site}/quality", "site_id": site, "entity_id": "pump-01", "occurred_at": occurred_at, "schema_version": 1, "schema_ref": "industrial.outcome.v1", "payload": {"campaign_id": campaign_id, "episode_id": episode_ids[site], "outcome_id": outcome_id, "action_id": action_id, "metric": "pressure_stability", "value": 0.96, "unit": "ratio", "success": True, "observed_at": occurred_at, "reward": 0.96}}
                    action_file.write(json.dumps({**action["payload"], "event_id": action["event_id"], "occurred_at": occurred_at, "site_id": site}) + "\n")
                    outcome_file.write(json.dumps({**outcome["payload"], "event_id": outcome["event_id"], "observed_at": occurred_at, "site_id": site}) + "\n")
                    action_rows.append(action); outcome_rows.append(outcome)
                    operational_ids.extend([action["event_id"], outcome["event_id"]])
                    _publish(producer, "industrial.operational", f"{site}/action", action, counters)
                    _publish(producer, "industrial.operational", f"{site}/outcome", outcome, counters)
                if sample_index % 30 == 0:
                    body = f"simulated-thermal-frame site={site} sample={sample_index}\n".encode()
                    key = f"world-model-soak/{campaign_id}/{site}/artifact-{artifact_count}.bin"
                    digest = _upload_artifact(client, "lakehouse", key, body)
                    reference = {"artifact_id": f"{campaign_id}-{site}-artifact-{artifact_count}", "event_id": str(uuid.uuid4()), "campaign_id": campaign_id, "site_id": site, "source_id": f"{site}/thermal-camera", "entity_id": "pump-01", "modality": "thermal", "uri": f"s3://lakehouse/{key}", "sha256": digest, "size_bytes": len(body), "content_type": "application/octet-stream", "encoding": "binary", "started_at": occurred_at, "ended_at": occurred_at, "clock_id": "world-model-soak-clock", "calibration_version": "cal-1", "topology_version": "topology-1", "schema_version": 1, "episode_id": episode_ids[site], "lineage_id": episode_ids[site]}
                    artifact_file.write(json.dumps(reference) + "\n")
                    artifact_rows.append(reference)
                    _publish(producer, "industrial.observation-artifacts", f"{site}/artifact", reference, counters)
                    artifact_count += 1
            sample_index += 1
            next_sample += 1.0 / args.telemetry_rate
        for site in sites:
            boundary_event_id = str(uuid.uuid4())
            boundary = {"event_id": boundary_event_id, "event_type": "episode.ended", "event_kind": "boundary", "source_id": "world-model-soak", "site_id": site, "entity_id": "pump-01", "occurred_at": _utc(), "schema_version": 1, "schema_ref": "industrial.boundary.v1", "payload": {"campaign_id": campaign_id, "episode_id": episode_ids[site], "boundary_type": "end", "reason": "soak-complete", "step": sample_index}}
            operational_ids.append(boundary_event_id)
            episode_rows.append({"event_id": boundary_event_id, "site_id": site, "episode_id": episode_ids[site], "boundary_type": "end", "occurred_at": boundary["occurred_at"], "campaign_id": campaign_id, "step": sample_index})
            _publish(producer, "industrial.operational", site, boundary, counters)
    producer.flush(30)

    episode_source = root / "episodes.jsonl"
    episode_source.write_text("\n".join(json.dumps(row) for row in episode_rows) + "\n", encoding="utf-8")
    manifest = {"manifest_version": 3, "dataset_id": campaign_id, "site_ids": sites, "time_range": {"start": campaign_started_at, "end": _utc()}, "purpose": "dreamer", "observation_sources": str(observations), "action_sources": str(actions), "outcome_sources": str(outcomes), "artifact_sources": str(artifacts), "episode_sources": str(episode_source), "episode_definition": {"boundary": "industrial.boundary.v1"}, "alignment": {"sample_interval_ms": 1000, "max_skew_ms": 600}, "splits": {"strategy": "explicit", "assignments": {episode_ids[sites[0]]: "train", episode_ids[sites[1]]: "validation", episode_ids[sites[2]]: "test"} if len(sites) == 3 else {episode_ids[site]: "train" for site in sites}}, "provenance": {"source": "world-model-soak", "campaign_id": campaign_id, "protocols": ["opcua", "mqtt", "modbus"]}, "semantic_context": {"topology_version": "topology-1", "sites": sites}}
    manifest_path = root / "manifest.yaml"
    import yaml
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    bundle_result = compile_trajectory_bundle(manifest_path, root / "bundle")
    bundle_counts = bundle_result.get("quality", {}).get("record_counts", {})
    expected_operational = len(action_rows) + len(outcome_rows) + len(sites) * 2
    evidence_complete = (
        bundle_counts.get("observations") == sample_index * len(sites) * len(channels)
        and bundle_counts.get("actions") == len(action_rows)
        and bundle_counts.get("outcomes") == len(outcome_rows)
        and bundle_counts.get("artifacts") == len(artifact_rows)
        and bundle_counts.get("episodes") == len(sites)
        and bundle_counts.get("transitions") == max(0, sample_index - 1) * len(sites)
        and bundle_counts.get("channels") == len(sites) * len(channels)
    )
    downstream = {"status": "skipped"}
    if not args.skip_downstream_verify:
        downstream = {
            "timescale": _verify_timescale(observation_ids, operational_ids),
            "lakehouse": _verify_lakehouse(operational_ids, [str(row["artifact_id"]) for row in artifact_rows]),
            "minio": _verify_minio(client, artifact_rows),
            "flink": _verify_flink(),
        }
    downstream_passed = args.skip_downstream_verify or all(item.get("status") == "passed" for item in downstream.values())
    report = {"campaign_id": campaign_id, "duration_seconds": round(time.monotonic() - started, 3), "configured_sites": sites, "sample_count": sample_index, "telemetry_records": sample_index * len(sites) * len(channels), "operational_records": expected_operational, "action_records": len(action_rows), "outcome_records": len(outcome_rows), "artifact_records": len(artifact_rows), "kafka": counters, "bundle": bundle_result, "downstream": downstream, "evidence_complete": evidence_complete, "passed": counters["failed"] == 0 and bundle_result["valid"] and evidence_complete and downstream_passed and sample_index >= max(1, args.seconds - 2)}
    (root / "world-model-soak.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (Path(args.report_dir) / "latest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
