# PLC Sensor Compatibility Matrix

## Goal

Track which PLC and sensor families the platform should be compatible with, and where gateways are the better answer.

## Current Direct Support

- OPC UA
- Modbus TCP
- Modbus RTU
- MQTT
- Sparkplug B
- API ingest
- dataset replay
- mock generators

## Gateway-First Families

- EtherNet/IP
- PROFINET
- vendor-specific PLC stacks
- smart sensor networks with proprietary encodings

## Compatibility Rules

- preserve `site`, `line`, `source_protocol`, `source_id`, `asset_id`, and `tag`
- keep protocol quirks at the adapter edge
- normalize into one internal industrial event contract
- keep multiple PLCs and sensors separate unless a correlation rule explicitly bridges them

## Known Edge Cases

- node-id and namespace drift in OPC UA
- register map and byte-order mismatches in Modbus
- QoS and topic drift in MQTT
- birth/death and versioning semantics in Sparkplug B
- cyclic versus acyclic data in industrial Ethernet families

## Next Refactor

- centralize tag and unit semantics in shared helpers
- keep PLC protocol metadata in one shared catalog
- document gateway patterns before adding more vendor-specific adapters

