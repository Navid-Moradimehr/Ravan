# Ravan Release Identity

- Current public release target: `1.0.0-beta.1`.
- License: Apache-2.0.
- Repository: https://github.com/Navid-Moradimehr/Ravan
- Source CLI aliases: `ravanctl`, `ravand`, `ravan-import`.
- Compatibility aliases remain: `datastreamctl`, `datastreamd`,
  `datastream-import`.
- Docker users must not need host Python; Compose wrappers will execute the
  operator CLI in a container. Native installers will embed the approved
  runtime.
- Existing Docker volume names remain unchanged during beta hardening to
  protect current local Kafka, historian, MinIO, and Grafana data.
- CI validates Python, Compose, Helm, and the UI build. Tagged releases publish
  a checksummed source bundle and release manifest; installers and signed image
  distribution remain deferred.
