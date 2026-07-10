from __future__ import annotations

import asyncio
from typing import Any

from services.edge_ingest.publisher import EdgePublisher
from services.edge_ingest.settings import Settings

from .mqtt import run_mqtt
from .modbus import run_modbus
from .modbus_rtu import run_modbus_rtu
from .opcua import run_opcua
from .opcua_discovery import run_opcua_discovery


def build_connector_tasks(settings: Settings, publisher: EdgePublisher, stop_event: asyncio.Event) -> list[asyncio.Task[None]]:
    tasks: list[asyncio.Task[None]] = []
    for source in settings.source_connections():
        if source.source_protocol == "mqtt":
            tasks.append(asyncio.create_task(run_mqtt(settings, publisher, stop_event, source)))
        elif source.source_protocol == "opcua":
            tasks.append(asyncio.create_task(run_opcua(settings, publisher, stop_event, source)))
        elif source.source_protocol == "modbus":
            tasks.append(asyncio.create_task(run_modbus(settings, publisher, stop_event, source)))
        elif source.source_protocol == "modbus_rtu":
            tasks.append(asyncio.create_task(run_modbus_rtu(settings, publisher, stop_event, source)))
        elif source.source_protocol == "opcua_discovery":
            tasks.append(asyncio.create_task(run_opcua_discovery(settings, publisher, stop_event, source)))
    return tasks
