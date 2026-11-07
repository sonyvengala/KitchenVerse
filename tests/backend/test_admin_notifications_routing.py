"""
Tests for Admin Notifications routing and browser redirection.
Verifies:
- Browsers requesting /admin/notifications with Accept: text/html are redirected to FRONTEND_URL/admin/notifications.
- API requests with Accept: application/json receive JSON responses directly.
- Frontend Admin Portal route integration.
"""
import pytest
from fastapi.testclient import TestClient
from backend.app.core.config import settings


def test_browser_navigating_to_admin_notifications_redirects_to_frontend(client: TestClient):
    """
    When a user opens http://localhost:8000/admin/notifications in their browser,
    the browser sends Accept: text/html.
    The backend redirects the user to the Frontend Admin Portal (http://localhost:3000/admin/notifications).
    """
    res = client.get(
        "/admin/notifications",
        headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
        follow_redirects=False
    )
    assert res.status_code == 307
    expected_frontend = f"{settings.FRONTEND_URL.rstrip('/')}/admin/notifications"
    assert res.headers["location"] == expected_frontend


def test_api_client_requesting_admin_notifications_returns_json(client: TestClient):
    """
    When an API client (or frontend fetch) requests /admin/notifications,
    Accept is application/json. It receives the JSON API response (or 401 if unauthenticated).
    """
    res = client.get(
        "/admin/notifications",
        headers={"Accept": "application/json"},
        follow_redirects=False
    )
    # Without auth cookie/header, require_admin returns 401 JSON, NOT a redirect
    assert res.status_code == 401
    assert "application/json" in res.headers["content-type"]
    assert "detail" in res.json()
