# Implementation Report - 2026-07-10

## Changes completed

The deployment-hardening work is complete for the parts that can be validated
without physical PLCs or sensors.

1. Source connection commissioning now supports persisted source definitions,
   bounded diagnostics, OPC UA read-only preview, declarative Modbus register
   configuration, Sparkplug B binary decoding, source mappings, and legacy
   environment fallback.
2. Per-source health is exposed through Prometheus and now retains bounded
   state-transition history when `EDGE_SOURCE_HEALTH_HISTORY_PATH` is set.
   The API exposes current state and recent history at
   `/api/v1/observability/source-health`.
3. Edge store-and-forward is available through `EDGE_STORE_FORWARD_DIR` for
   synchronous Kafka publication failures. It is not a replacement for Kafka
   replication or backups.
4. Sink routing is persisted through `/api/v1/sinks` and supports existing
   historian, Kafka, and lakehouse sink implementations. Explicit `SINKS`
   environment configuration remains authoritative. File-backed routes reload
   between fan-out batches when that override is absent.
5. Webhook and Apprise delivery status is retained in a bounded, redacted
   ledger. This provides delivery visibility without creating a new queue or
   storing provider credentials.
6. Docker Compose now shares the health and routing state correctly, and the
   API probes the AI gateway through `ai-gateway:8080` rather than its own
   container localhost address.

## Effects

### Reliability

- Source failures are visible by connection, protocol, and site instead of
  only as aggregate process logs.
- State transitions survive edge process restarts when the optional history
  path is mounted on durable storage.
- Synchronous Kafka publication failures can be replayed from the edge spool.
- Sink route changes no longer require container recreation when API-managed
  routing is used.
- Notification operators can distinguish failed delivery from unconfigured
  delivery.

### Maintainability

- Existing sink and connector implementations remain the source of truth;
  registries only hold deployment metadata.
- No new microservice, broker, identity provider, or mandatory external
  catalog was introduced.
- Existing environment configuration remains backward compatible.

### Performance

These changes are primarily reliability and deployment changes. They should
not be expected to improve hot-path throughput. Durable history writes occur
only on source state transitions, not on every successful event. Sink route
reload checks are lightweight and occur in the fan-out loop.

## Verification

- Python tests: `504 passed, 4 warnings`.
- Docker Compose configuration: passed.
- Docker images rebuilt and affected services restarted.
- API health: `200`, status `ok` after correcting the internal AI gateway
  address.
- Source health API: `200`, returning persisted edge transitions.
- Sink route API: `200`.
- Integrations UI and edge metrics: `200`.
- Next.js production build: passed in the preceding verification pass.

## Benchmark results

The benchmark uses simulated industrial events and measures local processing;
it does not validate PLC protocol behavior, broker durability, historian disk
throughput, or multi-site networking.

| Run | Average throughput | p99 latency | Invalid events |
| --- | ---: | ---: | ---: |
| Real-world simulator, six cases | 49,833 events/s | n/a | 0 |
| End-to-end JSON, one run | 33,483 events/s | 0.0397 ms | 0 |
| JSON, five-run repeatability | 34,272 events/s | 0.0432 ms average | 0 |
| MessagePack, five-run repeatability | 28,227 events/s | 0.0779 ms average | 0 |

The five-run spread is significant enough that the implementation should not
claim a stable MessagePack improvement from this workstation. Benchmark
results vary with local CPU scheduling and background Docker load. The
reliable conclusion is zero invalid events and stable functional behavior,
not a production capacity number.

## Intentionally remaining user-owned work

- Physical PLC/sensor compatibility and protocol commissioning at a real site
- Network routing, certificates, credentials, broker ACLs, retention, and
  backups
- Site-specific Kafka partition sizing and TimescaleDB capacity planning
- Guaranteed asynchronous notification queues, if a company requires them
- Real multi-site failure, network partition, and recovery rehearsals

The last item is intentionally not implemented as an internal queue. A
company that needs crash-safe notification retries can connect its own queue
or notification gateway while keeping the platform's notification contract.
