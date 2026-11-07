"""
End-to-end integration tests for customer registration, email verification,
password reset security, and order email workflows.
All tests run against isolated in-memory SQLite database with mocked SMTP transports
to guarantee zero live internet emails and zero mutation of business data.
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from itsdangerous import URLSafeTimedSerializer

from backend.app.core.config import settings
from backend.app.core.email import EmailService, email_service
from backend.app.models.user import User, KitchenProfile
from backend.app.models.enums import UserRole


@pytest.fixture
def email_svc():
    svc = EmailService()
    svc.provider = "smtp"
    return svc


def test_customer_registration_and_email_verification_e2e(client: TestClient, db_session: Session):
    """
    Audit 1 & 2 & 3:
    - Customer registers
    - Verification email is dispatched with 'KitchenVerse Support' sender
    - Verification token is verified, single-use, and cleared upon use
    """
    test_email = "audit.customer@example.com"
    payload = {
        "email": test_email,
        "password": "StrongTestPass123!",
        "full_name": "Audit Customer",
        "phone_number": "+919999888877",
        "dietary_preferences": "Vegan"
    }

    with patch.object(email_service, "send_verification_email_sync") as mock_send:
        mock_send.return_value = {"status": "sent", "provider": "smtp"}

        res = client.post("/api/v1/auth/register", json=payload)
        assert res.status_code == 201

        # Confirm verification email was dispatched
        assert mock_send.call_count == 1
        called_email, verification_url = mock_send.call_args[0]
        assert called_email == test_email
        assert "/verify-email?token=" in verification_url

        # Check sender details in settings
        assert settings.sender_display_name == "KitchenVerse Support"
        assert "sonyvengala04@gmail.com" in settings.sender_email_address

    # Verify user state in DB
    user = db_session.query(User).filter(User.email == test_email).first()
    assert user is not None
    assert user.is_verified is False
    token = user.verification_token
    assert token is not None

    # Step 2: Confirm verification via /verify-email endpoint
    verify_res = client.post("/api/v1/auth/verify-email", json={"token": token})
    assert verify_res.status_code == 200
    assert "verified" in verify_res.json()["message"].lower()

    # Step 3: Confirm user state is now verified and token is cleared (single-use)
    db_session.refresh(user)
    assert user.is_verified is True
    assert user.verification_token is None

    # Step 4: Confirm single-use protection - Re-submitting the same token MUST be rejected
    second_verify = client.post("/api/v1/auth/verify-email", json={"token": token})
    assert second_verify.status_code == 400
    assert any(w in second_verify.json()["detail"].lower() for w in ["already used", "already verified", "invalid"])


def test_verification_token_expiration(client: TestClient, db_session: Session):
    """Confirm verification tokens expired (> 24 hours) are rejected."""
    import time
    email = "expired.token@example.com"
    reg_payload = {
        "email": email,
        "password": "StrongTestPass123!",
        "full_name": "Expired Test User",
    }
    res = client.post("/api/v1/auth/register", json=reg_payload)
    assert res.status_code == 201

    user = db_session.query(User).filter(User.email == email).first()
    token = user.verification_token
    assert token is not None

    # Simulate 25 hours into the future (max_age is 24 hours / 86400 seconds)
    future_time = time.time() + (25 * 3600)
    with patch("time.time", return_value=future_time):
        verify_res = client.post("/api/v1/auth/verify-email", json={"token": token})
        assert verify_res.status_code == 400
        assert "expired" in verify_res.json()["detail"].lower()


def test_verification_token_tampered_rejected(client: TestClient):
    """Confirm forged or tampered tokens are rejected."""
    tampered_token = "eyJhbGciOi.tampered_payload_signature_broken.fake"
    verify_res = client.post("/api/v1/auth/verify-email", json={"token": tampered_token})
    assert verify_res.status_code == 400
    assert "invalid" in verify_res.json()["detail"].lower()


def test_forgot_password_token_security_and_single_use(client: TestClient, db_session: Session):
    """
    Confirm forgot-password workflow:
    - 1-hour expiration
    - Single-use (cleared on reset)
    - Replay protection
    """
    email = "reset.audit@example.com"
    client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "InitialPassword123!",
        "full_name": "Reset Audit User",
    })

    with patch.object(email_service, "send_password_reset_email_sync") as mock_reset_email:
        mock_reset_email.return_value = {"status": "sent", "provider": "smtp"}

        # Request reset
        forgot_res = client.post("/api/v1/auth/forgot-password", json={"email": email})
        assert forgot_res.status_code == 200
        # Token is never in response body (security requirement)
        assert "token" not in forgot_res.json() or forgot_res.json().get("token") is None

        # Verify email call
        assert mock_reset_email.call_count == 1
        called_email, reset_url = mock_reset_email.call_args[0]
        assert called_email == email
        assert "/reset-password?token=" in reset_url

    user = db_session.query(User).filter(User.email == email).first()
    reset_token = user.password_reset_token
    expires_at = user.password_reset_expires
    assert reset_token is not None
    assert expires_at is not None
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    # Confirm expiration window is within 1 hour
    assert expires_at > datetime.now(timezone.utc)
    assert expires_at <= datetime.now(timezone.utc) + timedelta(hours=1, minutes=1)

    # Perform password reset
    reset_res = client.post("/api/v1/auth/reset-password", json={
        "token": reset_token,
        "new_password": "NewUpdatedPassword123!"
    })
    assert reset_res.status_code == 200

    # Token must be cleared (single-use)
    db_session.refresh(user)
    assert user.password_reset_token is None
    assert user.password_reset_expires is None

    # Replay attack: submitting same token again MUST fail
    replay_res = client.post("/api/v1/auth/reset-password", json={
        "token": reset_token,
        "new_password": "AnotherPassword123!"
    })
    assert replay_res.status_code == 400


def test_order_email_workflows_formatting(email_svc):
    """
    Test customer order confirmation and kitchen notification email templates
    and headers using the configured KitchenVerse Support sender.
    """
    from email.utils import parseaddr
    from unittest.mock import AsyncMock

    with patch("aiosmtplib.send", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = ({}, "250 OK")

        # 1. Customer order placed email
        r_cust = email_svc.send_order_placed_customer_email_sync(
            to_email="customer@example.com",
            order_number="ORD-TEST-999",
            kitchen_name="Biryani Express",
            total_amount=520.0
        )
        assert r_cust["status"] == "sent"

        # Verify From header
        msg_cust = mock_send.call_args[0][0]
        disp_name, addr = parseaddr(msg_cust["From"])
        assert disp_name == "KitchenVerse Support"
        assert addr == settings.sender_email_address
        assert "Order Placed #ORD-TEST-999" in msg_cust["Subject"]
        body_cust = msg_cust.get_payload()[0].get_payload(decode=True).decode("utf-8")
        assert "₹520.00" in body_cust

        # 2. Kitchen owner notification email
        r_kitchen = email_svc.send_order_placed_kitchen_email_sync(
            to_email="owner@example.com",
            order_number="ORD-TEST-999",
            total_amount=520.0,
            items_summary="2x Hyderabadi Chicken Biryani"
        )
        assert r_kitchen["status"] == "sent"

        msg_kitchen = mock_send.call_args[0][0]
        disp_name_k, addr_k = parseaddr(msg_kitchen["From"])
        assert disp_name_k == "KitchenVerse Support"
        assert addr_k == settings.sender_email_address
        assert "New Order Received #ORD-TEST-999" in msg_kitchen["Subject"]
        body_kitchen = msg_kitchen.get_payload()[0].get_payload(decode=True).decode("utf-8")
        assert "2x Hyderabadi Chicken Biryani" in body_kitchen
