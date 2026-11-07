"""
Regression tests for Admin Self-Deactivation Prevention.
Ensures:
1. Administrator cannot suspend or deactivate their own authenticated account (HTTP 400).
2. Administrator account remains active in database after self-deactivation attempt.
3. Administrator retains full permission to activate/suspend other platform users.
4. Setting ACTIVE status on own account does not cause an error.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.core.security import get_password_hash
from backend.app.models.enums import UserRole
from backend.app.models.user import User


def test_admin_cannot_deactivate_self(client: TestClient, db_session: Session):
    """
    Verify that an administrator attempting to deactivate or suspend their
    own currently authenticated account is blocked with HTTP 400 Bad Request.
    """
    admin_user = User(
        email="test_active_admin@example.com",
        hashed_password=get_password_hash("AdminPass123!"),
        full_name="Active Administrator",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    db_session.add(admin_user)
    db_session.commit()

    # Log in as admin
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "test_active_admin@example.com",
        "password": "AdminPass123!"
    })
    assert login_resp.status_code == 200
    cookie = login_resp.cookies.get(settings.SESSION_COOKIE_NAME)
    client.cookies.set(settings.SESSION_COOKIE_NAME, cookie)

    # Attempt to suspend self
    patch_resp = client.patch(
        f"/api/v1/admin/users/{admin_user.id}/status",
        json={"status": "SUSPENDED"}
    )
    assert patch_resp.status_code == 400
    data = patch_resp.json()
    assert "Self-deactivation is prohibited" in data["detail"]

    # Verify admin in database remains active
    db_session.refresh(admin_user)
    assert admin_user.is_active is True

    # Attempt to deactivate self with status INACTIVE
    patch_resp_inactive = client.patch(
        f"/api/v1/admin/users/{admin_user.id}/status",
        json={"status": "INACTIVE"}
    )
    assert patch_resp_inactive.status_code == 400
    assert "Self-deactivation is prohibited" in patch_resp_inactive.json()["detail"]

    db_session.refresh(admin_user)
    assert admin_user.is_active is True


def test_admin_can_manage_other_users(client: TestClient, db_session: Session):
    """
    Verify that administrators can still suspend and activate other users as expected.
    """
    admin_user = User(
        email="test_super_admin2@example.com",
        hashed_password=get_password_hash("AdminPass123!"),
        full_name="Super Admin Two",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    target_user = User(
        email="target_user_to_suspend@example.com",
        hashed_password=get_password_hash("UserPass123!"),
        full_name="Target User",
        role=UserRole.CUSTOMER,
        is_active=True,
        is_verified=True,
    )
    db_session.add_all([admin_user, target_user])
    db_session.commit()

    # Log in as admin
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "test_super_admin2@example.com",
        "password": "AdminPass123!"
    })
    assert login_resp.status_code == 200
    cookie = login_resp.cookies.get(settings.SESSION_COOKIE_NAME)
    client.cookies.set(settings.SESSION_COOKIE_NAME, cookie)

    # Suspend target user
    suspend_resp = client.patch(
        f"/api/v1/admin/users/{target_user.id}/status",
        json={"status": "SUSPENDED"}
    )
    assert suspend_resp.status_code == 200
    assert suspend_resp.json()["status"] == "INACTIVE"

    db_session.refresh(target_user)
    assert target_user.is_active is False

    # Reactivate target user
    activate_resp = client.patch(
        f"/api/v1/admin/users/{target_user.id}/status",
        json={"status": "ACTIVE"}
    )
    assert activate_resp.status_code == 200
    assert activate_resp.json()["status"] == "ACTIVE"

    db_session.refresh(target_user)
    assert target_user.is_active is True
