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

