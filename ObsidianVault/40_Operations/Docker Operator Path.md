# Docker Operator Path

Status: implemented for the source-release Compose path.

- Docker-native `ravan` and `ravanctl` wrappers remove the host Python
  requirement for normal operators.
- Production starts the UI and edge ingestion but excludes protocol simulators.
- Simulators are now explicit `demo` profile services.
- Flink remains the production runtime; Python fallback stays explicit.
- Dataset workers can use a standard `DATABASE_URL` without duplicated
  Timescale-specific environment variables.

Next: validate the production wrapper and JMX metrics against a rebuilt Compose
stack, then complete Helm identity/runtime cleanup.
