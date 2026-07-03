# PLC And Sensor Compatibility Matrix

This project is intended to work with as many industrial edge devices as possible without requiring a cloud dependency.
The practical strategy is to support the most common industrial transport families first, then keep the stream contract
stable so vendor-specific tags, nodes, and register maps can be normalized into the same event envelope.

## Protocol Families

### OPC UA

Best fit for heterogeneous plants and mixed vendors.

- official interoperability standard for industrial automation
- supports profile-based conformance, which matters because PLCs and servers often expose different capability subsets
- good choice when you need structured tags, browsing, subscriptions, and security

Edge cases to handle:

- namespace and node-id drift between vendors
- certificate trust and renewal
- subscription sampling limits on smaller PLCs

### Modbus TCP and Modbus RTU

Best fit for brownfield retrofits, meters, RTUs, and simple PLC integrations.

- Modbus is designed for exchanging process data between industrial control devices
- the protocol is simple, widely supported, and easy to bridge
- Modbus RTU remains important where serial RS-485 wiring is already in place

Edge cases to handle:

- register map ambiguity
- byte and word order differences
- serial framing and baud mismatches
- shared bus contention

### MQTT and Sparkplug B

Best fit for edge gateways and plant-to-platform pub/sub topologies.

- MQTT gives lightweight transport and site-to-site fan-out
- Sparkplug B adds a stricter industrial contract with device lifecycle semantics

Edge cases to handle:

- topic design drift
- QoS consistency across brokers
- payload versioning
- birth/death state handling

### EtherNet/IP And PROFINET

These are major industrial Ethernet families that appear frequently in real plants.
The current codebase does not speak them directly, so the practical plan is to terminate them at a gateway
or vendor connector and normalize the payload into the same internal event contract.

Why they matter:

- EtherNet/IP is built on CIP and is common in manufacturing and process automation
- PROFINET is a widely used industrial Ethernet standard with a modular function set and strong diagnostics

Edge cases to handle through a gateway:

- cyclic versus acyclic data separation
- device diagnostics and quality bits
- topology changes and device replacement

## Sensor Layer Guidance

The platform should treat sensors as payload sources attached to one of the transport families above.
For example:

- temperature, vibration, pressure, flow, and current sensors often arrive via Modbus, OPC UA, MQTT, or a PLC gateway
- smart sensors may be bridged through an IO gateway rather than wired directly into the platform
- vibration and condition-monitoring sensors are especially useful for predictive-maintenance datasets and should keep source identity intact

## Compatibility Rules For The Platform

1. Keep `site`, `line`, `source_protocol`, `source_id`, `asset_id`, and `tag` stable across every ingest path.
2. Normalize vendor tags into the shared runtime envelope instead of mutating the source protocol shape.
3. Keep protocol-specific quirks in the edge adapter, not in historian storage.
4. Prefer explicit gateways for EtherNet/IP, PROFINET, and other vendor-specific stacks that are not directly modeled in the core service.
5. Preserve raw source identity so multiple PLCs or sensors can remain separate while still being correlated later.

## Current Code Coverage

- direct support: OPC UA, MQTT, Modbus TCP, Modbus RTU, Sparkplug B, API ingest, dataset replay, mock generators
- indirect support: vendor-specific PLC and sensor networks via gateways or protocol bridges
- future candidates: direct EtherNet/IP connector, direct PROFINET connector, more vendor-specific sensor adapters

## Open-Source Sources Consulted

- OPC Foundation OPC UA overview and specification pages
- Modbus Organization specification and introduction pages
- ODVA EtherNet/IP and CIP pages
- PROFIBUS & PROFINET International specification and overview pages

