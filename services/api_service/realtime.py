from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder

from services.common.runtime_metrics import observe_websocket_batch_delivery
from services.common.service_health import ServiceHealthState


router = APIRouter()
service_state = ServiceHealthState(name="api-service")


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        async with self._lock:
            connections = list(self.active_connections)
        encoded_message = jsonable_encoder(message)
        for conn in connections:
            try:
                await conn.send_json(encoded_message)
            except Exception:
                dead.append(conn)
        if dead:
            async with self._lock:
                for conn in dead:
                    if conn in self.active_connections:
                        self.active_connections.remove(conn)

    async def send_personal(self, websocket: WebSocket, message: dict[str, Any]) -> None:
        try:
            await websocket.send_json(jsonable_encoder(message))
        except Exception:
            await self.disconnect(websocket)


alarm_manager = ConnectionManager()
event_manager = ConnectionManager()
telemetry_manager = ConnectionManager()


async def _alarm_broadcaster() -> None:
    from services.historian.client import query_alarms

    last_data: list[dict[str, Any]] = []
    while True:
        try:
            data = query_alarms(50)
            if data != last_data:
                last_data = data
                service_state.mark_ok()
                observe_websocket_batch_delivery("alarms", data)
                await alarm_manager.broadcast({"type": "update", "alarms": data})
        except Exception as exc:
            service_state.mark_degraded("alarm broadcast failure", str(exc))
        await asyncio.sleep(2.0)


async def _event_broadcaster() -> None:
    from services.historian.client import query_recent_events as query_historian_events

    last_data: dict[str, list[dict[str, Any]]] = {}
    tables = ["industrial_events", "processed_events", "ai_enriched"]
    while True:
        for table in tables:
            try:
                data = query_historian_events(table, 100)
                if data != last_data.get(table):
                    last_data[table] = data
                    service_state.mark_ok()
                    observe_websocket_batch_delivery(f"historian:{table}", data)
                    await event_manager.broadcast({"type": "update", "table": table, "events": data})
            except Exception as exc:
                service_state.mark_degraded(f"event broadcast failure:{table}", str(exc))
        await asyncio.sleep(2.0)


async def _telemetry_broadcaster() -> None:
    from services.ai_gateway.main import _build_telemetry

    while True:
        try:
            payload = await _build_telemetry()
            service_state.mark_ok()
            await telemetry_manager.broadcast({"type": "update", "telemetry": payload})
        except Exception as exc:
            service_state.mark_degraded("telemetry broadcast failure", str(exc))
        await asyncio.sleep(5.0)


async def _heartbeat_task() -> None:
    while True:
        await asyncio.sleep(15.0)
        await alarm_manager.broadcast({"type": "heartbeat"})
        await event_manager.broadcast({"type": "heartbeat"})
        await telemetry_manager.broadcast({"type": "heartbeat"})


def create_realtime_tasks() -> list[asyncio.Task[None]]:
    return [
        asyncio.create_task(_alarm_broadcaster()),
        asyncio.create_task(_event_broadcaster()),
        asyncio.create_task(_telemetry_broadcaster()),
        asyncio.create_task(_heartbeat_task()),
    ]


@router.websocket("/ws/alarms")
async def websocket_alarms(websocket: WebSocket) -> None:
    await alarm_manager.connect(websocket)
    try:
        from services.historian.client import query_alarms

        data = query_alarms(50)
        observe_websocket_batch_delivery("alarms", data)
        await websocket.send_json(jsonable_encoder({"type": "init", "alarms": data}))
        while True:
            msg = await websocket.receive_text()
            try:
                parsed = json.loads(msg)
                if parsed.get("action") == "ping":
                    await websocket.send_json({"type": "pong"})
                elif parsed.get("action") == "subscribe":
                    data = query_alarms(50)
                    await websocket.send_json(jsonable_encoder({"type": "init", "alarms": data}))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        await alarm_manager.disconnect(websocket)


@router.websocket("/ws/events")
async def websocket_events(websocket: WebSocket) -> None:
    await event_manager.connect(websocket)
    try:
        from services.historian.client import query_recent_events as query_historian_events

        for table in ["industrial_events", "processed_events", "ai_enriched"]:
            data = query_historian_events(table, 100)
            observe_websocket_batch_delivery(f"historian:{table}", data)
            await websocket.send_json(jsonable_encoder({"type": "init", "table": table, "events": data}))
        while True:
            msg = await websocket.receive_text()
            try:
                parsed = json.loads(msg)
                if parsed.get("action") == "ping":
                    await websocket.send_json({"type": "pong"})
                elif parsed.get("action") == "subscribe":
                    table = parsed.get("table", "industrial_events")
                    data = query_historian_events(table, 100)
                    await websocket.send_json(jsonable_encoder({"type": "init", "table": table, "events": data}))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        await event_manager.disconnect(websocket)


@router.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket) -> None:
    await telemetry_manager.connect(websocket)
    try:
        from services.ai_gateway.main import _build_telemetry

        payload = await _build_telemetry()
        await websocket.send_json(jsonable_encoder({"type": "init", "telemetry": payload}))
        while True:
            msg = await websocket.receive_text()
            try:
                parsed = json.loads(msg)
                if parsed.get("action") == "ping":
                    await websocket.send_json({"type": "pong"})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        await telemetry_manager.disconnect(websocket)
