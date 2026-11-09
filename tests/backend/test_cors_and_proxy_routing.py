"""
Tests for Demand Forecasting & Platform Production Routing / CORS Security:
1. Allowed & disallowed CORS origins (exact prod domain, localhost, narrowly scoped previews, rejecting arbitrary *.vercel.app).
2. Vercel proxy routing rules in vercel.json (/api/:path* -> Render before SPA fallback).
3. Frontend production URL resolution (same-origin '' on Vercel/dev, preserving intentional VITE_API_URL overrides).
"""
import json
import os
import subprocess
import uuid
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from backend.app.main import app
from backend.app.core.config import Settings, settings
from backend.app.core.security import get_password_hash
from backend.app.core.session import create_user_session
from backend.app.models.enums import UserRole
from backend.app.models.user import User


ROOT_DIR = Path(__file__).resolve().parents[2]
VERCEL_JSON_PATH = ROOT_DIR / "vercel.json"
API_TS_PATH = ROOT_DIR / "src" / "lib" / "api.ts"
WS_TS_PATH = ROOT_DIR / "src" / "services" / "websocketService.ts"
ENV_EXAMPLE_PATH = ROOT_DIR / ".env.example"


def test_cors_settings_preserve_localhost_and_production_domain():
    """Even when CORS_ORIGINS only sets production URL, localhost dev origins and prod URL remain allowed."""
    custom_settings = Settings(CORS_ORIGINS="https://kitchen-verse-pi.vercel.app")
    origins = custom_settings.cors_origins_list

    assert "https://kitchen-verse-pi.vercel.app" in origins
    assert "http://localhost:3000" in origins
    assert "http://localhost:5173" in origins
    assert "http://127.0.0.1:3000" in origins
    assert "http://127.0.0.1:5173" in origins

    # Ensure unrestricted wildcard regex is NOT used
    assert settings.CORS_ORIGIN_REGEX != r"^https://.*\.vercel\.app$"
    assert r".*\.vercel\.app" not in settings.CORS_ORIGIN_REGEX


@pytest.mark.parametrize(
    "allowed_origin",
    [
        "https://kitchen-verse-pi.vercel.app",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "https://kitchen-verse-git-master-sonyvengala.vercel.app",
        "https://kitchen-verse-a1b2c3d4e-sonyvengala.vercel.app",
        "https://kitchen-verse-pi-git-fix-cors-team.vercel.app",
    ],
)
def test_cors_preflight_allows_kitchenverse_and_localhost_origins(allowed_origin: str):
    """Allowed KitchenVerse production, narrowly scoped previews, and localhost origins pass CORS preflight."""
    client = TestClient(app)
    resp = client.options(
        "/api/v1/ml/forecast",
        headers={
            "Origin": allowed_origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert resp.status_code == 200, f"Expected 200 for {allowed_origin}, got {resp.status_code}: {resp.text}"
    assert resp.headers.get("access-control-allow-origin") == allowed_origin
    assert resp.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.parametrize(
    "disallowed_origin",
    [
        "https://evil.vercel.app",
        "https://other-kitchen-verse.vercel.app",
        "https://kitchen-verse.vercel.app",
        "https://kitchen-verse-evil.vercel.app",
        "https://kitchen-verse-pi.vercel.app.evil.com",
        "http://kitchen-verse-pi.vercel.app",
        "https://attacker.com",
    ],
)
def test_cors_preflight_and_get_reject_disallowed_origins(disallowed_origin: str):
    """Disallowed or arbitrary *.vercel.app origins are rejected with 400 and receive no CORS allow header."""
    client = TestClient(app)
    preflight = client.options(
        "/api/v1/ml/forecast",
        headers={
            "Origin": disallowed_origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert preflight.status_code == 400
    assert "access-control-allow-origin" not in preflight.headers

    get_resp = client.get(
        "/api/v1/ml/info",
        headers={"Origin": disallowed_origin},
    )
    assert get_resp.status_code == 200
    assert "access-control-allow-origin" not in get_resp.headers


def test_vercel_proxy_routing_rewrites_api_to_render_before_spa_fallback():
    """Verify vercel.json proxies /api/:path* to Render before the SPA catch-all rule."""
    assert VERCEL_JSON_PATH.exists(), "vercel.json must exist at repository root"
    config = json.loads(VERCEL_JSON_PATH.read_text(encoding="utf-8"))
    rewrites = config.get("rewrites", [])
    assert len(rewrites) >= 2

    api_idx = next((i for i, r in enumerate(rewrites) if r.get("source") == "/api/:path*"), None)
    health_idx = next((i for i, r in enumerate(rewrites) if r.get("source") == "/health"), None)
    uploads_idx = next((i for i, r in enumerate(rewrites) if r.get("source") == "/uploads/:path*"), None)
    spa_idx = next((i for i, r in enumerate(rewrites) if r.get("source") == "/(.*)"), None)

    assert api_idx is not None, "/api/:path* rewrite must be present in vercel.json"
    assert health_idx is not None, "/health rewrite must be present in vercel.json"
    assert uploads_idx is not None, "/uploads/:path* rewrite must be present in vercel.json"
    assert spa_idx is not None, "SPA catch-all /(.*) rewrite must be present in vercel.json"

    assert rewrites[api_idx]["destination"] == "https://kitchenverse.onrender.com/api/:path*"
    assert rewrites[health_idx]["destination"] == "https://kitchenverse.onrender.com/health"
    assert rewrites[uploads_idx]["destination"] == "https://kitchenverse.onrender.com/uploads/:path*"
    assert rewrites[spa_idx]["destination"] == "/"

    # Proxy rewrites must come BEFORE SPA fallback
    assert api_idx < spa_idx
    assert health_idx < spa_idx
    assert uploads_idx < spa_idx


def test_frontend_production_url_resolution_and_overrides():
    """
    Transpile and execute resolveApiBaseUrl from src/lib/api.ts via TypeScript & Node
    to verify same-origin ('') on browser deployments while preserving VITE_API_URL overrides.
    """
    assert API_TS_PATH.exists()
    node_script = r"""
    const fs = require('fs');
    const vm = require('vm');
    const ts = require('typescript');
    const assert = require('assert');

    const rawSource = fs.readFileSync(process.argv[1], 'utf8')
      .replace('import.meta.env.VITE_API_URL', 'undefined');

    const compiled = ts.transpileModule(rawSource, {
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2020,
      }
    }).outputText;

    const moduleObj = { exports: {} };
    const sandbox = {
      module: moduleObj,
      exports: moduleObj.exports,
      require,
      URL,
      console,
      window: undefined,
    };
    vm.runInNewContext(compiled, sandbox);

    const { resolveApiBaseUrl } = moduleObj.exports;
    assert.strictEqual(typeof resolveApiBaseUrl, 'function');

    // 1. Browser runtime without VITE_API_URL (both localhost dev and Vercel production) -> same-origin ''
    assert.strictEqual(resolveApiBaseUrl(undefined, true), '');
    assert.strictEqual(resolveApiBaseUrl('', true), '');
    assert.strictEqual(resolveApiBaseUrl('   ', true), '');

    // 2. Intentional VITE_API_URL overrides preserved (and trailing slashes stripped)
    assert.strictEqual(resolveApiBaseUrl('https://kitchenverse.onrender.com', true), 'https://kitchenverse.onrender.com');
    assert.strictEqual(resolveApiBaseUrl('https://staging-api.example.com/', true), 'https://staging-api.example.com');
    assert.strictEqual(resolveApiBaseUrl('http://localhost:8000/', true), 'http://localhost:8000');

    // 3. Node/SSR fallback without window
    assert.strictEqual(resolveApiBaseUrl(undefined, false), 'http://localhost:8000');
    console.log('FRONTEND_URL_RESOLUTION_OK');
    """
    res = subprocess.run(
        ["node", "-e", node_script, str(API_TS_PATH)],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        check=True,
    )
    assert "FRONTEND_URL_RESOLUTION_OK" in res.stdout

    # Ensure websocketService preserves wss://kitchenverse.onrender.com on remote browser when apiBase is ''
    ws_text = WS_TS_PATH.read_text(encoding="utf-8")
    assert "wss://kitchenverse.onrender.com" in ws_text

    # Ensure .env.example leaves VITE_API_URL empty by default
    env_text = ENV_EXAMPLE_PATH.read_text(encoding="utf-8")
    assert "\nVITE_API_URL=\n" in env_text or env_text.endswith("\nVITE_API_URL=")


def _create_ws_test_session(db_session: Session) -> str:
    uid = uuid.uuid4().hex[:10]
    user = User(
        id=f"ws_user_{uid}",
        email=f"ws_user_{uid}@kitchenverse.local",
        hashed_password=get_password_hash("WsTestPass123!"),
        full_name="WebSocket Origin Tester",
        role=UserRole.CUSTOMER,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    session = create_user_session(db_session, user.id)
    return session.session_id


@pytest.mark.parametrize(
    "allowed_origin",
    [
        "https://kitchen-verse-pi.vercel.app",
        "http://localhost:3000",
        "http://localhost:5173",
        "https://kitchen-verse-git-master-sonyvengala.vercel.app",
    ],
)
def test_websocket_accepts_trusted_origins(client: TestClient, db_session: Session, allowed_origin: str):
    """WebSocket handshake accepts production Vercel, localhost, and scoped preview origins."""
    token = _create_ws_test_session(db_session)
    with client.websocket_connect(
        f"/api/v1/ws?token={token}",
        headers={"Origin": allowed_origin},
    ) as ws:
        handshake = ws.receive_json()
        assert handshake["type"] == "CONNECTION_ESTABLISHED"


@pytest.mark.parametrize(
    "untrusted_origin",
    [
        "https://evil.vercel.app",
        "https://other-kitchen-verse.vercel.app",
        "https://kitchen-verse.vercel.app",
        "https://kitchen-verse-evil.vercel.app",
        "https://kitchen-verse-pi.vercel.app.evil.com",
        "http://kitchen-verse-pi.vercel.app",
        "https://attacker.com",
        "null",
        "",
    ],
)
def test_websocket_rejects_untrusted_origins(client: TestClient, db_session: Session, untrusted_origin: str):
    """WebSocket handshake rejects untrusted, spoofed, null, or empty Origin headers even with a valid token."""
    token = _create_ws_test_session(db_session)
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            f"/api/v1/ws?token={token}",
            headers={"Origin": untrusted_origin},
        ):
            pass
    assert exc_info.value.code == 1008


