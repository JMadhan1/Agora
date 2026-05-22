"""Oracle Sentinel WebSocket handler — real-time push to dashboard clients."""
import json
import asyncio
from typing import List

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

log = structlog.get_logger()

router = APIRouter()


class ConnectionManager:
    """Manages all active WebSocket connections and broadcasts messages."""

    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        log.info("ws_client_connected", total=len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        log.info("ws_client_disconnected", total=len(self.active_connections))

    async def broadcast(self, message: dict) -> None:
        """Send a JSON message to every connected client, dropping stale connections."""
        payload = json.dumps(message)
        dead: List[WebSocket] = []
        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception:
                dead.append(connection)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        # Send initial handshake so the client knows it's connected.
        await websocket.send_text(
            json.dumps({"type": "connected", "message": "Oracle Sentinel live feed active"})
        )
        while True:
            # Keep the connection alive; clients may send pings.
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                msg = {"raw": data}
            # Echo back any ping messages.
            if msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as exc:
        log.warning("ws_error", error=str(exc))
        manager.disconnect(websocket)


async def broadcast_attestation(attestation_data: dict) -> None:
    """Push a new attestation event to all connected dashboard clients."""
    await manager.broadcast(
        {
            "type": "attestation",
            "data": attestation_data,
        }
    )


async def broadcast_alert(alert_data: dict) -> None:
    """Push a dispute alert event to all connected dashboard clients."""
    await manager.broadcast(
        {
            "type": "alert",
            "data": alert_data,
        }
    )
