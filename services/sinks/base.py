"""Sink protocol, composite, and registry for endpoint-dataset fan-out.

The platform historically wrote directly from processors into the historian
(TimescaleDB) and into Kafka topics. That couples the processing path to
specific endpoints and makes it hard to support different downstream datasets
(lakehouse, operational dashboards, third-party systems) in an open-source
context where users bring their own endpoints.

Sinks decouple the *what is produced* (normalized/validated events) from the
*where it lands*: a processor hands a batch to a :class:`CompositeSink`, which
fans it to every registered sink. New endpoints are added by implementing the
:class:`Sink` protocol and registering them in :class:`SinkRegistry.from_env`.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class Sink(Protocol):
    """Write batches of normalized events to an endpoint dataset.

    Implementations must be safe to call concurrently from the fan-out
    dispatcher but are not required to be internally buffered; the caller is
    responsible for batching.
    """

    name: str

    def write_batch(self, events: list[dict[str, Any]]) -> int:
        """Persist a batch of events. Returns the number accepted."""
        ...

    def flush(self) -> None:
        """Flush any internal buffers to the endpoint."""
        ...

    def close(self) -> None:
        """Release endpoint resources (connections, producers)."""
        ...


class CompositeSink:
    """Fan one batch to many sinks, isolating per-sink failures.

    If one sink fails, the others still receive the batch and the failure is
    logged + counted so a single bad endpoint cannot stall the whole pipeline.
    """

    def __init__(self, sinks: list[Sink] | None = None) -> None:
        self._sinks: list[Sink] = list(sinks or [])

    @property
    def sinks(self) -> list[Sink]:
        return list(self._sinks)

    def add(self, sink: Sink) -> None:
        self._sinks.append(sink)

    def write_batch(self, events: list[dict[str, Any]]) -> int:
        if not events:
            return 0
        accepted = 0
        for sink in self._sinks:
            try:
                accepted += sink.write_batch(events)
            except Exception as exc:  # pragma: no cover - endpoint failure path
                logger.warning("sink %s write_batch failed: %s", getattr(sink, "name", sink), exc)
        return accepted

    def write_batch_strict(self, events: list[dict[str, Any]]) -> int:
        """Write to every configured sink and fail if any endpoint rejects data."""
        if not events:
            return 0
        accepted = 0
        failures: list[str] = []
        for sink in self._sinks:
            sink_name = str(getattr(sink, "name", sink))
            try:
                sink_accepted = sink.write_batch(events)
                accepted += sink_accepted
                if sink_accepted != len(events):
                    failures.append(f"{sink_name} accepted {sink_accepted}/{len(events)}")
            except Exception as exc:
                failures.append(f"{sink_name}: {exc}")
        if failures:
            raise RuntimeError("; ".join(failures))
        return accepted

    def flush(self) -> None:
        for sink in self._sinks:
            try:
                sink.flush()
            except Exception as exc:  # pragma: no cover
                logger.warning("sink %s flush failed: %s", getattr(sink, "name", sink), exc)

    def flush_strict(self) -> None:
        """Flush every configured sink and fail if any endpoint fails."""
        failures: list[str] = []
        for sink in self._sinks:
            sink_name = str(getattr(sink, "name", sink))
            try:
                strict_flush = getattr(sink, "flush_strict", None)
                if callable(strict_flush):
                    strict_flush()
                else:
                    sink.flush()
            except Exception as exc:
                failures.append(f"{sink_name}: {exc}")
        if failures:
            raise RuntimeError("; ".join(failures))

    def close(self) -> None:
        for sink in self._sinks:
            try:
                sink.close()
            except Exception as exc:  # pragma: no cover
                logger.warning("sink %s close failed: %s", getattr(sink, "name", sink), exc)

    def __enter__(self) -> "CompositeSink":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class SinkRegistry:
    """Build a :class:`CompositeSink` from environment configuration.

    Enabled via ``SINKS`` (comma-separated sink names). Each sink may carry its
    own env configuration; see the individual sink modules.
    """

    @staticmethod
    def from_env(env: dict[str, str] | None = None) -> CompositeSink:
        env = env or {k: v for k, v in os.environ.items()}
        names = [n.strip().lower() for n in env.get("SINKS", "").split(",") if n.strip()]
        routing_path = env.get("DATASTREAM_SINK_ROUTING_PATH", "")
        if routing_path and not names:
            try:
                from services.common.sink_routing import SinkRouteRegistry

                names = SinkRouteRegistry(routing_path).enabled_sink_types()
            except Exception as exc:
                logger.warning("sink routing registry could not be loaded: %s", exc)
        composite = CompositeSink()
        for name in names:
            sink = SinkRegistry._build(name, env)
            if sink is not None:
                composite.add(sink)
        return composite

    @staticmethod
    def _build(name: str, env: dict[str, str]) -> Sink | None:
        try:
            if name == "historian":
                from services.sinks.historian_sink import TimescaleHistorianSink

                return TimescaleHistorianSink.from_env(env)
            if name == "kafka":
                from services.sinks.kafka_sink import KafkaSink

                return KafkaSink.from_env(env)
            if name == "lakehouse":
                from services.sinks.lakehouse import LakehouseSink

                return LakehouseSink.from_env(env)
        except Exception as exc:  # pragma: no cover - misconfiguration path
            logger.warning("sink %s could not be built: %s", name, exc)
            return None
        logger.warning("unknown sink name: %s", name)
        return None
