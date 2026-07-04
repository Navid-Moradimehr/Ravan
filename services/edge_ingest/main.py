from __future__ import annotations

import asyncio
import signal
from prometheus_client import start_http_server

from services.common.normalize import to_legacy_iot_event

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

    tasks = build_connector_tasks(settings, publisher, stop_event)

    try:
        await stop_event.wait()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        publisher.flush()


if __name__ == "__main__":
    asyncio.run(main())
