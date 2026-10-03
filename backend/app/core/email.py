"""Configurable email service supporting SMTP, SendGrid, and console output."""
import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailServiceError(Exception):
    """Raised when email service is not properly configured."""
    pass


class EmailService:
    """
    Configurable email service.
    
    Supports:
    - 'console': Logs emails to stdout (development)
    - 'smtp': Sends via SMTP server
    - 'sendgrid': Sends via SendGrid API
    
    If the provider is not configured, raises EmailServiceError.
    """

    def __init__(self):
        self.provider = settings.EMAIL_PROVIDER
        self.from_email = settings.EMAIL_FROM

    async def send_verification_email(self, to_email: str, verification_url: str) -> dict:
        """Send an email verification link."""
        subject = "Verify your email address"
        html_body = f"""
        <html>
        <body>
            <h2>Welcome to {settings.APP_NAME}!</h2>
            <p>Please verify your email address by clicking the link below:</p>
            <p><a href="{verification_url}">Verify Email Address</a></p>
            <p>This link will expire in 24 hours.</p>
            <p>If you did not create an account, please ignore this email.</p>
        </body>
        </html>
        """
        return await self._send(to_email, subject, html_body)

    async def send_password_reset_email(self, to_email: str, reset_url: str) -> dict:
        """Send a password reset link."""
        subject = "Reset your password"
        html_body = f"""
        <html>
        <body>
            <h2>Password Reset Request</h2>
            <p>You requested a password reset. Click the link below:</p>
            <p><a href="{reset_url}">Reset Password</a></p>
            <p>This link will expire in 1 hour.</p>
            <p>If you did not request this, please ignore this email.</p>
        </body>
        </html>
        """
        return await self._send(to_email, subject, html_body)

    async def _send(self, to_email: str, subject: str, html_body: str) -> dict:
        """Route email to the configured provider."""
        if self.provider == "console":
            return await self._send_console(to_email, subject, html_body)
        elif self.provider == "smtp":
            return await self._send_smtp(to_email, subject, html_body)
        elif self.provider == "sendgrid":
            return await self._send_sendgrid(to_email, subject, html_body)
        else:
            raise EmailServiceError(
                f"Email provider '{self.provider}' is not supported. "
                "Use 'console', 'smtp', or 'sendgrid'."
            )

    async def _send_console(self, to_email: str, subject: str, html_body: str) -> dict:
        """Log email to console (development mode)."""
        logger.info(f"[EMAIL - CONSOLE] To: {to_email}")
        logger.info(f"[EMAIL - CONSOLE] Subject: {subject}")
        logger.info(f"[EMAIL - CONSOLE] Body: {html_body[:200]}...")
        return {
            "status": "logged",
            "provider": "console",
            "to": to_email,
            "subject": subject,
            "message": "Email logged to console (not actually sent)"
        }

    async def _send_smtp(self, to_email: str, subject: str, html_body: str) -> dict:
        """Send email via SMTP."""
        if not settings.SMTP_HOST:
            raise EmailServiceError(
                "SMTP provider selected but SMTP_HOST is not configured. "
                "Set SMTP_HOST, SMTP_PORT, SMTP_USER, and SMTP_PASSWORD in environment."
            )

        try:
            import aiosmtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            message = MIMEMultipart("alternative")
            message["From"] = self.from_email
            message["To"] = to_email
            message["Subject"] = subject
            message.attach(MIMEText(html_body, "html"))

            await aiosmtplib.send(
                message,
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                username=settings.SMTP_USER,
                password=settings.SMTP_PASSWORD,
                use_tls=True,
            )
            return {
                "status": "sent",
                "provider": "smtp",
                "to": to_email,
                "subject": subject
            }
        except Exception as e:
            raise EmailServiceError(f"SMTP send failed: {str(e)}")

    async def _send_sendgrid(self, to_email: str, subject: str, html_body: str) -> dict:
        """Send email via SendGrid API."""
        if not settings.SENDGRID_API_KEY:
            raise EmailServiceError(
                "SendGrid provider selected but SENDGRID_API_KEY is not configured."
            )

        try:
            import httpx

            response = await httpx.AsyncClient().post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={
                    "Authorization": f"Bearer {settings.SENDGRID_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "personalizations": [{"to": [{"email": to_email}]}],
                    "from": {"email": self.from_email},
                    "subject": subject,
                    "content": [{"type": "text/html", "value": html_body}],
                },
            )
            response.raise_for_status()
            return {
                "status": "sent",
                "provider": "sendgrid",
                "to": to_email,
                "subject": subject
            }
        except Exception as e:
            raise EmailServiceError(f"SendGrid send failed: {str(e)}")


# Singleton instance
email_service = EmailService()
