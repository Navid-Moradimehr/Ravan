from __future__ import annotations

import asyncio
import logging
import os
import signal
from pathlib import Path
from typing import Any
from prometheus_client import start_http_server

from services.common.normalize import to_legacy_iot_event


logger = logging.getLogger(__name__)

async def main() -> None:
    from services.edge_ingest.connectors import build_connector_tasks
    from services.edge_ingest.publisher import EdgePublisher
    from services.edge_ingest.settings import Settings

    settings = Settings()
    stop_event = asyncio.Event()
    publisher = EdgePublisher(settings, batch_size=settings.historian_batch_size)
    start_http_server(settings.metrics_port)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            # Windows event loops do not support signal handlers here.
            pass

    tasks: list[asyncio.Task[None]] = []

    async def reconcile_connectors() -> None:
        """Reload registry desired state without restarting the edge service."""
        nonlocal tasks
        registry_path = Path(os.getenv("DATASTREAM_CONNECTION_REGISTRY_PATH", ".datastream/connection-registry.json"))
        last_signature: tuple[Any, ...] | None = None
        while not stop_event.is_set():
            try:
                configured = settings.source_connections()
                signature = tuple(
                    # Settings returns enabled runtime definitions only. The
                    # enabled flag belongs to the registry model, not the
                    # connector runtime projection.
                    (item.connection_id, item.config_version, item.source_protocol)
                    for item in configured
                )
                if signature != last_signature:
                    logger.info("connection registry changed, rebuilding %s connector tasks", len(configured))
                    for task in tasks:
                        task.cancel()
                    if tasks:
                        await asyncio.gather(*tasks, return_exceptions=True)
                    tasks = build_connector_tasks(settings, publisher, stop_event)
                    last_signature = signature
            except Exception:
                # A malformed edit must not terminate the edge process.
                logger.exception("connector reconciliation failed")
            await asyncio.sleep(2.0 if registry_path.exists() else 5.0)

    async def service_publisher() -> None:
        """Flush partial batches even when every configured source is idle."""
        interval_seconds = max(0.05, min(publisher.flush_interval_seconds, 1.0))
        while not stop_event.is_set():
            try:
                publisher.service()
            except Exception:
                logger.exception("publisher service cycle failed")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
            except asyncio.TimeoutError:
                continue

    supervisor_task = asyncio.create_task(reconcile_connectors())
    publisher_task = asyncio.create_task(service_publisher())

    try:
        await stop_event.wait()
    finally:
        supervisor_task.cancel()
        publisher_task.cancel()
        await asyncio.gather(supervisor_task, publisher_task, return_exceptions=True)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        publisher.flush()


if __name__ == "__main__":
    asyncio.run(main())
