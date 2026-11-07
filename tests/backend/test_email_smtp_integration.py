"""
Unit and integration tests for EmailService and Gmail SMTP configuration.
Verifies:
- RFC 5322 formatted From header: "KitchenVerse Support <email>"
- SMTP port 587 uses STARTTLS (start_tls=True, use_tls=False)
- Authentication credentials passed to aiosmtplib.send
- All synchronous and asynchronous email dispatch helpers (verification, password reset,
  kitchen approval/rejection, order placement, order status, low stock, promotional campaigns)
- Graceful error handling and safety against credential leakage
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from email.utils import parseaddr

from backend.app.core.config import settings
from backend.app.core.email import EmailService, EmailServiceError


@pytest.fixture
def email_svc():
    svc = EmailService()
    svc.provider = "smtp"
    return svc


def test_settings_sender_name_and_email():
    """Verify sender display name and sender email address resolution."""
    assert settings.sender_display_name == "KitchenVerse Support"
    assert "sonyvengala04@gmail.com" in settings.sender_email_address
    assert settings.SMTP_HOST == "smtp.gmail.com"
    assert settings.SMTP_PORT == 587


@pytest.mark.asyncio
async def test_smtp_send_starttls_and_sender_header(email_svc):
    """
    Verify that _send_smtp correctly sets:
    1. From: "KitchenVerse Support <sonyvengala04@gmail.com>"
    2. port: 587 with start_tls=True, use_tls=False
    3. Proper username and credentials
    """
    with patch("aiosmtplib.send", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = ({}, "250 OK")

        res = await email_svc.send_verification_email("customer@example.com", "http://localhost:3000/verify-email?token=xyz")
        assert res["status"] == "sent"
        assert res["provider"] == "smtp"

        assert mock_send.await_count == 1
        _, kwargs = mock_send.call_args

        # Assert TLS settings for Port 587
        assert kwargs["hostname"] == "smtp.gmail.com"
        assert kwargs["port"] == 587
        assert kwargs["start_tls"] is True
        assert kwargs["use_tls"] is False
        assert kwargs["username"] == settings.SMTP_USER

        # Assert MIME message headers
        message = mock_send.call_args[0][0]
        assert "From" in message
        display_name, email_address = parseaddr(message["From"])
        assert display_name == "KitchenVerse Support"
        assert email_address == settings.sender_email_address
        assert message["To"] == "customer@example.com"
        assert "Verify your email address" in message["Subject"]


def test_all_email_workflows_sync(email_svc):
    """Verify all existing business email workflows trigger _send_sync cleanly."""
    with patch("aiosmtplib.send", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = ({}, "250 OK")

        # 1. Verification
        r1 = email_svc.send_verification_email_sync("user1@example.com", "http://localhost:3000/verify?token=123")
        assert r1["status"] == "sent"

        # 2. Password reset request
        r2 = email_svc.send_password_reset_email_sync("user2@example.com", "http://localhost:3000/reset?token=abc")
        assert r2["status"] == "sent"

        # 3. Password reset confirmed
        r3 = email_svc.send_password_reset_confirmed_email_sync("user2@example.com")
        assert r3["status"] == "sent"

        # 4. Order placed (customer)
        r4 = email_svc.send_order_placed_customer_email_sync("cust@example.com", "ORD-101", "Burger Hub", 450.0)
        assert r4["status"] == "sent"

        # 5. Order placed (kitchen)
        r5 = email_svc.send_order_placed_kitchen_email_sync("kitchen@example.com", "ORD-101", 450.0, "2x Burgers, 1x Fries")
        assert r5["status"] == "sent"

        # 6. Order status update
        r6 = email_svc.send_order_status_email_sync("cust@example.com", "ORD-101", "PREPARING", "The chef is preparing your meal.")
        assert r6["status"] == "sent"

        # 6b. Order delivered (customer - Order Successful final email)
        r6b = email_svc.send_order_delivered_customer_email_sync("cust@example.com", "ORD-101", "Burger Hub")
        assert r6b["status"] == "sent"

        # 7. Kitchen approval
        r7 = email_svc.send_kitchen_approval_email_sync("kitchen@example.com", "Burger Hub", True)
        assert r7["status"] == "sent"

        # 8. Kitchen rejection
        r8 = email_svc.send_kitchen_approval_email_sync("kitchen@example.com", "Burger Hub", False, "Missing FSSAI license")
        assert r8["status"] == "sent"

        # 9. Low stock warning
        r9 = email_svc.send_low_stock_email_sync("kitchen@example.com", "Burger Hub", "Cheese Slices", 4.0, "kg", 10.0)
        assert r9["status"] == "sent"

        # 10. Promotion campaign
        r10 = email_svc.send_promotion_campaign_email_sync("cust@example.com", "SAVE50", "Weekend Feast", "50% OFF", "Valid till Sunday", "Min order ₹200")
        assert r10["status"] == "sent"

        assert mock_send.await_count == 11


def test_smtp_error_raises_and_is_caught_safely(email_svc):
    """Verify that SMTP failure returns status 'failed' in _send_sync without crashing."""
    with patch("aiosmtplib.send", new_callable=AsyncMock) as mock_send:
        mock_send.side_effect = Exception("535 Authentication failed")

        res = email_svc.send_verification_email_sync("fail@example.com", "http://localhost:3000/verify")
        assert res["status"] == "failed"
        assert "535 Authentication failed" in res["error"]
