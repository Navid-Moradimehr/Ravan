"""Sink abstractions for fanning normalized events out to endpoint datasets.

A :class:`Sink` writes batches of validated/normalized events to an endpoint
(TimescaleDB historian, a downstream Kafka topic, an Iceberg lakehouse, ...).
The :class:`CompositeSink` fans one batch to many sinks, and the
:class:`SinkRegistry` builds a composite from environment configuration so the
platform can target different endpoint datasets without changing processor code.
"""

from __future__ import annotations

from services.sinks.base import CompositeSink, Sink, SinkRegistry

__all__ = ["Sink", "CompositeSink", "SinkRegistry"]
