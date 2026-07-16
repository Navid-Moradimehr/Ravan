# Source Onboarding and Runtime Activation

## What the platform owns

The connection registry owns non-secret connection metadata, protocol selection,
site identity, mappings, and desired enabled state. The API stores this metadata
in `/data/connection-registry.json` in Docker Compose. Credentials remain
deployment-owned references such as `env://OPCUA_PASSWORD` or a mounted
`file:///run/secrets/plant-a.json`; secret values are rejected from the registry.

The edge service reads the same registry. It watches connection IDs, config
versions, enabled state, and protocol. When one changes, it cancels and rebuilds
the affected connector task set without restarting the edge container. This is a
small in-process supervisor, not a new microservice.

## User flow

1. Create a source through the source-management UI.
2. Select the protocol and complete its five guided steps. Add `env://` or `file://`
   references for secret values and `path://` references for certificate/key
   files. Add mappings from source fields to canonical asset and tag IDs.
3. Run validation, network test, and preview. These are separate checks; a
   successful network test does not mean that a usable sample has been mapped.
4. Press Enable in the source row. The registry version changes and the edge supervisor
   starts the supported connector.
5. Confirm source health, Kafka raw/normalized topics, processed events, and the
   historian. The platform does not silently create dashboard panels for every
   discovered signal; users choose the presentation and retention policy.

## Supported runtime boundary

The existing edge runtime directly activates MQTT, OPC UA, Modbus TCP/RTU, and
OPC UA discovery connectors. Sparkplug B can use the MQTT adapter's payload mode.
REST Pull and HTTP Push are runtime paths. File, dataset, and mock remain
reference-only definitions until their dedicated workflows are used. REST Pull
polls JSON and maps records into canonical events; HTTP Push accepts canonical
or source-shaped JSON through the enabled connection endpoint. Both reuse the
same Kafka/DLQ/historian fan-out contract as the native edge protocols.

The old environment variables remain valid for simple deployments with no
registry file. A configured enabled registry takes precedence over those legacy
sources.
