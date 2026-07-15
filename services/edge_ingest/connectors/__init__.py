from __future__ import annotations

import asyncio
import logging
from typing import Any

from services.edge_ingest.publisher import EdgePublisher
from services.edge_ingest.source_health import mark_source
from services.edge_ingest.settings import Settings

from .mqtt import run_mqtt
from .modbus import run_modbus
from .modbus_rtu import run_modbus_rtu
from .opcua import run_opcua
from .opcua_discovery import run_opcua_discovery
from services.common.connection_registry import RUNTIME_PROTOCOLS


logger = logging.getLogger(__name__)


async def _supervise_connector(
    task_name: str,
    runner,
    settings: Settings,
    publisher: EdgePublisher,
    stop_event: asyncio.Event,
    source,
) -> None:
    try:
        await runner(settings, publisher, stop_event, source)
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # pragma: no cover - unexpected connector failure path
        logger.exception("connector %s crashed for %s", task_name, getattr(source, "connection_id", "unknown"))
        if source is not None:
            try:
                mark_source(source.connection_id, source.source_protocol, source.site_id, "error", str(exc))
            except Exception:
                logger.warning("failed to record connector crash state for %s", getattr(source, "connection_id", "unknown"))
    finally:
        if stop_event.is_set() and source is not None:
            try:
                mark_source(source.connection_id, source.source_protocol, source.site_id, "stopped", "edge runtime stopped")
            except Exception:
                logger.debug("failed to record connector stop state for %s", getattr(source, "connection_id", "unknown"))


def build_connector_tasks(settings: Settings, publisher: EdgePublisher, stop_event: asyncio.Event) -> list[asyncio.Task[None]]:
    tasks: list[asyncio.Task[None]] = []
    for source in settings.source_connections():
        if source.source_protocol not in RUNTIME_PROTOCOLS:
            logger.warning(
                "skipping non-runtime source %s protocol=%s site=%s note=metadata-only",
                source.connection_id,
                source.source_protocol,
                source.site_id,
            )
            try:
                mark_source(source.connection_id, source.source_protocol, source.site_id, "error", "metadata-only source is not started by the edge runtime")
            except Exception:
                logger.debug("failed to mark metadata-only source state for %s", source.connection_id)
            continue
        if source.source_protocol == "mqtt" or source.source_protocol == "sparkplug_b":
            tasks.append(asyncio.create_task(_supervise_connector(source.connection_id, run_mqtt, settings, publisher, stop_event, source)))
        elif source.source_protocol == "opcua":
            tasks.append(asyncio.create_task(_supervise_connector(source.connection_id, run_opcua, settings, publisher, stop_event, source)))
        elif source.source_protocol == "modbus":
            tasks.append(asyncio.create_task(_supervise_connector(source.connection_id, run_modbus, settings, publisher, stop_event, source)))
        elif source.source_protocol == "modbus_rtu":
            tasks.append(asyncio.create_task(_supervise_connector(source.connection_id, run_modbus_rtu, settings, publisher, stop_event, source)))
        elif source.source_protocol == "opcua_discovery":
            tasks.append(asyncio.create_task(_supervise_connector(source.connection_id, run_opcua_discovery, settings, publisher, stop_event, source)))
    return tasks
