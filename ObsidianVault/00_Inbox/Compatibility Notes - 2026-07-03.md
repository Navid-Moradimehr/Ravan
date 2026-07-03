# Compatibility Notes - 2026-07-03

## What changed

- Added a shared PLC/sensor compatibility helper in `services/common/device_compat.py`
- Removed duplicated tag-to-unit and tag-to-legacy-field logic from the edge/runtime helpers
- Added a protocol matrix covering OPC UA, Modbus TCP/RTU, MQTT, Sparkplug B, EtherNet/IP, and PROFINET

## Direct support

- OPC UA
- Modbus TCP
- Modbus RTU
- MQTT
- Sparkplug B
- API ingest
- dataset replay
- mock generators

## Gateway-first families

- EtherNet/IP
- PROFINET
- vendor-specific PLC stacks
- smart sensors with proprietary payloads

## Operational rule

- keep source identity stable
- normalize at the edge
- bridge through gateways when the protocol is not native to the core service
- keep raw streams separate across PLCs and sensors unless a correlation rule explicitly joins them

## Refactor progress

- historian write/query helpers are now shared
- API and AI gateway health surfaces now expose degraded state
- Flink task handling is more tolerant of malformed input
- API realtime/WebSocket behavior now lives in a focused runtime module
- edge ingest is split into settings, publisher, and protocol connector modules
- remaining API router domains are split into focused modules and thin aggregators
- ingest path now avoids repeated model_dump/normalize work for the same event
- packaging is still deferred

## Benchmark rerun

- first run in this session was noisy and underperformed the previous baseline
- repeat run landed close to baseline, so there is no clear material win yet
- python-fallback repeat throughput was 42,259.28 events/sec
- flink-production throughput was 51,526.15 events/sec
- cgr-stream-slice repeat throughput was 52,640.64 events/sec
- mixed replay repeat throughput was 94,941.61 events/sec
- API/edge decomposition rerun maintained compatibility and did not introduce a meaningful hot-path regression
- python-fallback throughput improved to 44,155.47 events/sec
- flink-production throughput improved to 51,394.54 events/sec
- cgr-stream-slice throughput improved to 53,312.15 events/sec
- flink-runtime-slice throughput improved to 51,173.09 events/sec
- mixed replay throughput improved to 98,558.48 events/sec
- end-to-end JSON should be remeasured separately because this session used the production-pipeline wrapper instead of the direct end-to-end benchmark command
- python-fallback throughput improved to 43,419.63 events/sec
- flink-production throughput improved to 43,251.30 events/sec
- cgr-stream-slice throughput improved to 50,751.73 events/sec
- flink-runtime-slice throughput improved to 50,738.60 events/sec
- mixed replay throughput improved to 93,350.90 events/sec
- end-to-end JSON throughput moved down to 42,080.58 events/sec and should be repeated once before calling it a regression
