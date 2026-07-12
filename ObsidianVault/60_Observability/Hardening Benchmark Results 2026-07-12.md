# Hardening Benchmark Results 2026-07-12

The final hardening pass completed with `555 passed` Python tests and four
non-blocking dependency warnings. Deployment preflight passed.

The 10,000-event resilience campaign accepted 9,897 events, rejected 103
malformed events, queued and replayed 1,961 outage events, and ended with zero
unaccounted events and zero pending spool records. Peak measured process memory
was 4,651.56 KB.

The final 5-site campaign processed 25,000 events, queued and replayed 1,000
events per site, retained 25,000 unique central IDs, and found zero cross-site
events, duplicate central IDs, or site isolation errors. All 25,000 events were
normalized and scored.

Docker smoke verification returned HTTP 200 for API, AI gateway, dashboard
Historian, and Prometheus readiness. The Flink anomaly processor was RUNNING.

These results validate local contracts and the current simulated deployment.
They are not a substitute for real PLC, network, Kafka federation, lakehouse,
or long-duration plant validation.

The Docker-backed `industrial-soak --smoke` attempt exceeded the local command
timeout during stack rebuild/reconciliation before emitting a report. The
stack was healthy afterward and the API, dashboard, Prometheus, and Flink
checks passed. A longer dedicated soak window is still required for a true
live throughput/restart acceptance result.
