"""
Real-time WebSocket & HTTP Event Polling Endpoints.
KitchenVerse Platform.
"""
import json
import logging
import time
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.database import SessionLocal, get_db
from backend.app.core.deps import get_current_user
from backend.app.core.session import get_active_session
from backend.app.models.user import User
from backend.app.websockets.connection_manager import ws_manager

logger = logging.getLogger("kitchenverse.realtime_routes")

router = APIRouter(tags=["Realtime Events"])


def _extract_ws_token(websocket: WebSocket) -> Optional[str]:
    """Extract auth session token from query param, cookies, or auth header."""
    # 1. Query parameter (?token=...)
    token = websocket.query_params.get("token")
    if token and token.strip() and token.strip() not in ("null", "undefined", "cookie-session"):
        return token.strip()

    # 2. Cookie (HttpOnly session cookie)
    cookie_token = websocket.cookies.get(settings.SESSION_COOKIE_NAME)
    if cookie_token and cookie_token.strip():
        return cookie_token.strip()

    # 3. Header fallback
    auth_hdr = websocket.headers.get("authorization")
    if auth_hdr and auth_hdr.startswith("Bearer "):
        bearer_tok = auth_hdr[7:].strip()
        if bearer_tok not in ("null", "undefined", "cookie-session"):
            return bearer_tok

    return None


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    db: Session = Depends(get_db),
):
    """
    Authenticated WebSocket connection endpoint.
    Maintains heartbeat, routes role-based updates, and handles graceful disconnects.
    """
    token = _extract_ws_token(websocket)
    if not token:
        logger.warning("WebSocket rejected: No authentication token provided.")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication required")
        return

    # Validate active DB session
    user: Optional[User] = None
    kitchen_id: Optional[str] = None
    active_session = get_active_session(db, token)
    if not active_session:
        logger.warning(f"WebSocket rejected: Invalid or expired session {token[:8]}...")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Session invalid or expired")
        return

    user = db.query(User).filter(User.id == active_session.user_id).first()
    if not user or not user.is_active:
        logger.warning("WebSocket rejected: User account inactive or not found.")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User inactive")
        return

    if user.kitchen_profile:
        kitchen_id = user.kitchen_profile.id


    user_id = user.id
    user_role = user.role.value if hasattr(user.role, "value") else str(user.role)

    # Register in connection manager
    await ws_manager.connect(
        websocket=websocket,
        user_id=user_id,
        role=user_role,
        kitchen_id=kitchen_id,
    )

    try:
        while True:
            # Listen for client heartbeat/messages
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                mtype = msg.get("type", "").upper()
                if mtype == "PING":
                    await websocket.send_json({
                        "type": "PONG",
                        "timestamp": time.time(),
                        "echo": msg.get("data")
                    })
            except json.JSONDecodeError:
                if data.strip().upper() == "PING":
                    await websocket.send_json({
                        "type": "PONG",
                        "timestamp": time.time()
                    })
    except (WebSocketDisconnect, RuntimeError):
        logger.debug(f"Client disconnected: {user_id}")
    except Exception as e:
        logger.debug(f"WebSocket connection error for {user_id}: {e}")
    finally:
        ws_manager.disconnect(websocket)


@router.get("/events/poll")
def poll_events(
    since: float = Query(0.0, description="Epoch timestamp in seconds of the latest known event"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    HTTP long-polling fallback for environments where WebSockets are unavailable.
    Filters buffered real backend events using strict RBAC rules.
    """
    user_role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    kitchen_id = current_user.kitchen_profile.id if current_user.kitchen_profile else None

    events = ws_manager.get_events_since(
        since_timestamp=since,
        user_id=current_user.id,
        role=user_role,
        kitchen_id=kitchen_id,
    )

    return {
        "status": "success",
        "server_time": time.time(),
        "events": [
            {
                "id": ev["id"],
                "type": ev["event_type"],
                "timestamp": ev["timestamp"],
                "data": ev["data"],
            }
            for ev in events
        ]
    }


@router.get("/realtime/status")
def realtime_status(
    current_user: User = Depends(get_current_user),
):
    """Returns real-time connection diagnostic status."""
    return {
        "status": "active",
        "active_connections": len(ws_manager._active_connections),
        "buffered_events_count": len(ws_manager._event_buffer),
        "server_time": time.time(),
    }
