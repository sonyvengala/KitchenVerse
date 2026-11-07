"""
Central WebSocket Connection Manager & Real-Time Event Dispatcher.
KitchenVerse Platform.

Maintains active WebSocket connections grouped by user_id, role, and kitchen_id.
Provides thread-safe, transaction-safe event publication with an in-memory
ring buffer fallback for HTTP long-polling clients.
"""
import asyncio
from datetime import datetime, timezone
import json
import logging
import threading
import time
from typing import Dict, List, Optional, Set, Any
import uuid

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("kitchenverse.realtime")


def utc_timestamp() -> float:
    return time.time()


def utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ConnectionManager:
    def __init__(self, buffer_capacity: int = 1000):
        # Active connections: websocket -> metadata dict
        self._active_connections: Dict[WebSocket, Dict[str, Any]] = {}
        # Mappings for rapid routing
        self._user_connections: Dict[str, Set[WebSocket]] = {}
        self._role_connections: Dict[str, Set[WebSocket]] = {}
        self._kitchen_connections: Dict[str, Set[WebSocket]] = {}
        # Concurrency lock for connection registries
        self._lock = threading.Lock()
        # Main asyncio event loop reference
        self.main_loop: Optional[asyncio.AbstractEventLoop] = None
        # Ring buffer for event polling fallback
        self.buffer_capacity = buffer_capacity
        self._event_buffer: List[Dict[str, Any]] = []
        self._buffer_lock = threading.Lock()

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Register the running FastAPI asyncio loop."""
        self.main_loop = loop

    def get_event_loop(self) -> Optional[asyncio.AbstractEventLoop]:
        if self.main_loop and self.main_loop.is_running():
            return self.main_loop
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return None

    async def connect(
        self,
        websocket: WebSocket,
        user_id: str,
        role: str,
        kitchen_id: Optional[str] = None
    ) -> None:
        """Accept WebSocket connection and register user mapping."""
        try:
            current_loop = asyncio.get_running_loop()
            if not self.main_loop or not self.main_loop.is_running():
                self.main_loop = current_loop
        except RuntimeError:
            pass

        await websocket.accept()
        meta = {
            "user_id": user_id,
            "role": role.upper() if role else "CUSTOMER",
            "kitchen_id": kitchen_id,
            "connected_at": utc_timestamp(),
        }

        with self._lock:
            self._active_connections[websocket] = meta
            # User map
            if user_id not in self._user_connections:
                self._user_connections[user_id] = set()
            self._user_connections[user_id].add(websocket)
            # Role map
            norm_role = meta["role"]
            if norm_role not in self._role_connections:
                self._role_connections[norm_role] = set()
            self._role_connections[norm_role].add(websocket)
            # Kitchen map
            if kitchen_id:
                if kitchen_id not in self._kitchen_connections:
                    self._kitchen_connections[kitchen_id] = set()
                self._kitchen_connections[kitchen_id].add(websocket)

        logger.info(
            f"WebSocket connected: user_id={user_id}, role={meta['role']}, "
            f"kitchen_id={kitchen_id}. Active: {len(self._active_connections)}"
        )

        # Send initial connection handshake confirmation
        try:
            await websocket.send_json({
                "type": "CONNECTION_ESTABLISHED",
                "timestamp": utc_timestamp(),
                "data": {
                    "user_id": user_id,
                    "role": meta["role"],
                    "kitchen_id": kitchen_id,
                    "server_time": utc_iso_now(),
                }
            })
        except Exception as e:
            logger.warning(f"Error sending handshake: {e}")

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove disconnected WebSocket from all registries."""
        with self._lock:
            meta = self._active_connections.pop(websocket, None)
            if not meta:
                return

            user_id = meta.get("user_id")
            if user_id and user_id in self._user_connections:
                self._user_connections[user_id].discard(websocket)
                if not self._user_connections[user_id]:
                    del self._user_connections[user_id]

            role = meta.get("role")
            if role and role in self._role_connections:
                self._role_connections[role].discard(websocket)
                if not self._role_connections[role]:
                    del self._role_connections[role]

            kitchen_id = meta.get("kitchen_id")
            if kitchen_id and kitchen_id in self._kitchen_connections:
                self._kitchen_connections[kitchen_id].discard(websocket)
                if not self._kitchen_connections[kitchen_id]:
                    del self._kitchen_connections[kitchen_id]

        logger.info(
            f"WebSocket disconnected: user_id={user_id}. Active: {len(self._active_connections)}"
        )

    def append_to_buffer(self, event_record: Dict[str, Any]) -> None:
        """Append event to in-memory buffer with bounded capacity for polling fallback."""
        with self._buffer_lock:
            self._event_buffer.append(event_record)
            if len(self._event_buffer) > self.buffer_capacity:
                self._event_buffer = self._event_buffer[-self.buffer_capacity:]

    def get_events_since(
        self,
        since_timestamp: float,
        user_id: str,
        role: str,
        kitchen_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve buffered events newer than since_timestamp that the caller is authorized to see.
        Enforces strict RBAC:
        - ADMIN sees all events.
        - KITCHEN_OWNER sees events targeting their kitchen_id, their user_id, role KITCHEN_OWNER, or broadcast.
        - CUSTOMER sees events targeting their user_id, role CUSTOMER, or broadcast.
        """
        norm_role = (role or "").upper()
        results: List[Dict[str, Any]] = []

        with self._buffer_lock:
            for ev in self._event_buffer:
                if ev["timestamp"] <= since_timestamp:
                    continue

                # RBAC authorization check
                if norm_role == "ADMIN":
                    results.append(ev)
                    continue

                target_user = ev.get("target_user_id")
                target_role = ev.get("target_role")
                target_kitchen = ev.get("target_kitchen_id")
                is_broadcast = ev.get("broadcast_all", False)

                if is_broadcast:
                    results.append(ev)
                    continue

                if target_user and target_user == user_id:
                    results.append(ev)
                    continue

                if target_role and target_role.upper() == norm_role:
                    results.append(ev)
                    continue

                if kitchen_id and target_kitchen and target_kitchen == kitchen_id:
                    results.append(ev)
                    continue

        return results

    async def _send_to_sockets(self, sockets: Set[WebSocket], message: dict) -> None:
        """Send JSON payload to a set of sockets, cleaning up dead ones."""
        if not sockets:
            return
        dead_sockets: List[WebSocket] = []
        for ws in list(sockets):
            try:
                await ws.send_json(message)
            except (WebSocketDisconnect, RuntimeError, Exception) as e:
                logger.debug(f"Failed to send to WebSocket, marking for removal: {e}")
                dead_sockets.append(ws)

        if dead_sockets:
            for ws in dead_sockets:
                self.disconnect(ws)

    async def dispatch_event(self, event_record: Dict[str, Any]) -> None:
        """Route event payload asynchronously to targeted WebSockets."""
        msg = {
            "id": event_record["id"],
            "type": event_record["event_type"],
            "timestamp": event_record["timestamp"],
            "data": event_record["data"],
        }

        target_user = event_record.get("target_user_id")
        target_role = event_record.get("target_role")
        target_kitchen = event_record.get("target_kitchen_id")
        is_broadcast = event_record.get("broadcast_all", False)

        targets_to_send: Set[WebSocket] = set()

        with self._lock:
            if is_broadcast:
                targets_to_send.update(self._active_connections.keys())
            else:
                if target_user and target_user in self._user_connections:
                    targets_to_send.update(self._user_connections[target_user])

                if target_role:
                    norm_role = target_role.upper()
                    if norm_role in self._role_connections:
                        targets_to_send.update(self._role_connections[norm_role])

                if target_kitchen and target_kitchen in self._kitchen_connections:
                    targets_to_send.update(self._kitchen_connections[target_kitchen])

        if targets_to_send:
            await self._send_to_sockets(targets_to_send, msg)

    def publish_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        target_user_id: Optional[str] = None,
        target_role: Optional[str] = None,
        target_kitchen_id: Optional[str] = None,
        broadcast_all: bool = False,
    ) -> Dict[str, Any]:
        """
        Public synchronous dispatch helper.
        Safe to call from any sync or async context after DB transaction commits.
        1. Buffers event for HTTP polling fallback.
        2. Dispatches to active WebSockets without blocking DB callers.
        """
        event_record = {
            "id": str(uuid.uuid4()),
            "event_type": event_type,
            "timestamp": utc_timestamp(),
            "data": data,
            "target_user_id": target_user_id,
            "target_role": target_role.upper() if target_role else None,
            "target_kitchen_id": target_kitchen_id,
            "broadcast_all": broadcast_all,
        }

        # 1. Add to ring buffer for polling fallback
        self.append_to_buffer(event_record)

        # 2. Schedule async dispatch
        loop = self.get_event_loop()
        if loop and loop.is_running():
            try:
                # If currently running in the same event loop thread:
                asyncio.run_coroutine_threadsafe(self.dispatch_event(event_record), loop)
            except Exception as e:
                logger.warning(f"Failed scheduling dispatch_event: {e}")
        else:
            logger.debug("No active event loop available for WebSocket dispatch; buffered in memory.")

        return event_record


# Global singleton instance
ws_manager = ConnectionManager()
