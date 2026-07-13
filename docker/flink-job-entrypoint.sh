#!/usr/bin/env bash
set -euo pipefail

JOBMANAGER_URL="${FLINK_JOBMANAGER_URL:-http://jobmanager:8081}"
JOB_NAME="${FLINK_JOB_NAME:-iot-anomaly-processor}"

# Replace the job owned by this Compose deployment before submitting a new
# one. Otherwise every container recreate adds another Kafka consumer.
for _attempt in $(seq 1 30); do
  overview="$(curl -fsS "${JOBMANAGER_URL}/jobs/overview" 2>/dev/null || true)"
  if [ -n "$overview" ]; then
    job_ids="$(printf '%s' "$overview" | python3 -c "import json,sys; d=json.load(sys.stdin); print(' '.join(j.get('jid','') for j in d.get('jobs',[]) if j.get('name')==sys.argv[1] and j.get('state') in {'RUNNING','INITIALIZING','CREATED','RESTARTING','RECONCILING'}))" "$JOB_NAME")"
    if [ -z "$job_ids" ]; then
      break
    fi
    for job_id in $job_ids; do
      [ -z "$job_id" ] && continue
      curl -fsS -X PATCH "${JOBMANAGER_URL}/jobs/${job_id}?mode=cancel" >/dev/null || curl -fsS -X DELETE "${JOBMANAGER_URL}/jobs/${job_id}" >/dev/null || true
    done
    sleep 1
  fi
  sleep 1
done

exec flink run -m jobmanager:8081 \
  -py /opt/stream/services/processor/iot_anomaly_job.py \
  -pyfs /opt/stream
