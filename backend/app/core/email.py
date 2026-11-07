"""Configurable email service supporting SMTP, SendGrid, and console output."""
import logging
from typing import Optional

from backend.app.core.config import settings

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

    def __init__(self, provider: Optional[str] = None):
        self._provider = provider
        self.from_email = settings.EMAIL_FROM

    @property
    def provider(self) -> str:
        return self._provider or settings.EMAIL_PROVIDER

    @provider.setter
    def provider(self, val: Optional[str]):
        self._provider = val

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

    def send_verification_email_sync(self, to_email: str, verification_url: str) -> dict:
        """Send verification email synchronously."""
        subject = f"Verify your email — {settings.APP_NAME}"
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2>Welcome to {settings.APP_NAME}!</h2>
            <p>Please verify your email address by clicking the link below:</p>
            <p><a href="{verification_url}" style="display:inline-block;padding:10px 20px;background-color:#ea580c;color:#fff;text-decoration:none;border-radius:6px;font-weight:bold;">Verify Email Address</a></p>
            <p>Direct Link: {verification_url}</p>
            <p>This link expires in 24 hours.</p>
        </body>
        </html>
        """
        return self._send_sync(to_email, subject, html_body)

    def send_password_reset_email_sync(self, to_email: str, reset_url: str) -> dict:
        """Send password reset email synchronously."""
        subject = f"Password Reset Request — {settings.APP_NAME}"
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2>Password Reset Request</h2>
            <p>You requested a password reset for your {settings.APP_NAME} account.</p>
            <p><a href="{reset_url}" style="display:inline-block;padding:10px 20px;background-color:#ea580c;color:#fff;text-decoration:none;border-radius:6px;font-weight:bold;">Reset Password</a></p>
            <p>Direct Link: {reset_url}</p>
            <p>This link expires in 1 hour. If you did not request this, please ignore this email.</p>
        </body>
        </html>
        """
        return self._send_sync(to_email, subject, html_body)

    def send_password_reset_confirmed_email_sync(self, to_email: str) -> dict:
        """Send password reset confirmation email to user."""
        subject = f"Password Changed Successfully — {settings.APP_NAME}"
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2>Password Updated</h2>
            <p>Your password for {settings.APP_NAME} was successfully updated.</p>
            <p>All active sessions have been invalidated. If you did not make this change, please contact support immediately.</p>
        </body>
        </html>
        """
        return self._send_sync(to_email, subject, html_body)

    def send_order_placed_customer_email_sync(self, to_email: str, order_number: str, kitchen_name: str, total_amount: float) -> dict:
        """Send order confirmation email to customer."""
        subject = f"Order Placed #{order_number} — {settings.APP_NAME}"
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2>Thank you for your order!</h2>
            <p>Your order <strong>#{order_number}</strong> has been placed with <strong>{kitchen_name}</strong>.</p>
            <p><strong>Total Amount:</strong> ₹{total_amount:.2f}</p>
            <p>We will notify you once the kitchen accepts and begins preparing your food.</p>
        </body>
        </html>
        """
        return self._send_sync(to_email, subject, html_body)

    def send_order_placed_kitchen_email_sync(self, to_email: str, order_number: str, total_amount: float, items_summary: str) -> dict:
        """Send new order alert email to kitchen owner."""
        subject = f"New Order Received #{order_number} — {settings.APP_NAME}"
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2>New Order Alert!</h2>
            <p>You have received a new customer order <strong>#{order_number}</strong>.</p>
            <p><strong>Items:</strong> {items_summary}</p>
            <p><strong>Total Value:</strong> ₹{total_amount:.2f}</p>
            <p>Please log in to your Kitchen Portal to review and accept the order.</p>
        </body>
        </html>
        """
        return self._send_sync(to_email, subject, html_body)

    def send_order_status_email_sync(self, to_email: str, order_number: str, status_title: str, message: str) -> dict:
        """Send order status update email to customer."""
        subject = f"Order #{order_number} Update: {status_title} — {settings.APP_NAME}"
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2>Order Update</h2>
            <p><strong>Order Number:</strong> #{order_number}</p>
            <p><strong>Status:</strong> {status_title}</p>
            <p>{message}</p>
        </body>
        </html>
        """
        return self._send_sync(to_email, subject, html_body)

    def send_order_delivered_customer_email_sync(self, to_email: str, order_number: str, kitchen_name: str) -> dict:
        """Send final delivery confirmation email to customer (Order Successful)."""
        subject = f"Order Delivered Successfully #{order_number} — {settings.APP_NAME}"
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2 style="color: #10B981;">Order Delivered Successfully!</h2>
            <p>Your order <strong>#{order_number}</strong> from <strong>{kitchen_name}</strong> has been delivered. Enjoy your meal!</p>
            <p>Thank you for ordering with {settings.APP_NAME}. We hope you had a great dining experience!</p>
        </body>
        </html>
        """
        return self._send_sync(to_email, subject, html_body)


    def send_kitchen_approval_email_sync(self, to_email: str, kitchen_name: str, approved: bool, reason: Optional[str] = None) -> dict:
        """Send kitchen approval/rejection email to owner."""
        status_str = "Approved" if approved else "Application Update"
        subject = f"Kitchen {status_str}: {kitchen_name} — {settings.APP_NAME}"
        if approved:
            html_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <h2>Congratulations! Your Kitchen is Approved!</h2>
                <p>Your kitchen <strong>{kitchen_name}</strong> has been reviewed and approved by platform administrators.</p>
                <p>You can now configure your recipes, manage inventory, and start receiving customer orders.</p>
            </body>
            </html>
            """
        else:
            html_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <h2>Kitchen Application Update</h2>
                <p>Your application for kitchen <strong>{kitchen_name}</strong> was reviewed.</p>
                <p><strong>Decision:</strong> Not Approved</p>
                <p><strong>Reason:</strong> {reason or 'Does not meet current onboarding requirements.'}</p>
                <p>Please contact support for further guidance.</p>
            </body>
            </html>
            """
        return self._send_sync(to_email, subject, html_body)

    def send_low_stock_email_sync(self, to_email: str, kitchen_name: str, ingredient_name: str, current_stock: float, unit: str, threshold: float) -> dict:
        """Send low stock warning email to kitchen owner."""
        subject = f"Low Stock Warning: {ingredient_name} — {kitchen_name}"
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2 style="color: #c2410c;">Low Stock Alert</h2>
            <p>Your ingredient <strong>{ingredient_name}</strong> is running low at <strong>{kitchen_name}</strong>.</p>
            <p><strong>Current Stock:</strong> {current_stock:.2f} {unit}</p>
            <p><strong>Minimum Threshold:</strong> {threshold:.2f} {unit}</p>
            <p>Please restock soon to avoid running out during peak ordering hours.</p>
        </body>
        </html>
        """
        return self._send_sync(to_email, subject, html_body)

    def send_promotion_campaign_email_sync(self, to_email: str, promo_code: str, title: str, discount_text: str, expiry_text: str, min_order_text: str) -> dict:
        """Send promotional campaign offer email to an eligible customer."""
        subject = f"Exclusive Offer: Use code {promo_code} — {settings.APP_NAME}"
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2 style="color: #ea580c;">Special Promotional Offer!</h2>
            <p>Hello,</p>
            <p>Enjoy a special discount on your next delicious order at <strong>{settings.APP_NAME}</strong>!</p>
            <div style="background-color: #fff7ed; border: 2px dashed #ea580c; border-radius: 8px; padding: 16px; margin: 16px 0; text-align: center;">
                <h3 style="margin: 0; color: #9a3412;">{title}</h3>
                <p style="font-size: 24px; font-weight: bold; letter-spacing: 2px; color: #ea580c; margin: 8px 0;">{promo_code}</p>
                <p style="margin: 4px 0; font-size: 16px;"><strong>Discount:</strong> {discount_text}</p>
                <p style="margin: 4px 0; font-size: 14px; color: #666;">{min_order_text}</p>
                <p style="margin: 4px 0; font-size: 14px; color: #666;">{expiry_text}</p>
            </div>
            <p>Simply enter coupon code <strong>{promo_code}</strong> at checkout to apply your savings.</p>
            <p>Best regards,<br/>The {settings.APP_NAME} Team</p>
        </body>
        </html>
        """
        return self._send_sync(to_email, subject, html_body)

    def _send_sync(self, to_email: str, subject: str, html_body: str) -> dict:
        """Helper to send email safely with console/smtp/sendgrid support."""
        if self.provider == "console":
            import sys
            enc = sys.stdout.encoding or "utf-8"
            safe_subj = subject.encode(enc, errors="replace").decode(enc)
            safe_body = html_body.strip().encode(enc, errors="replace").decode(enc)
            print(f"\n==================== [CONSOLE EMAIL] ====================\nTo: {to_email}\nSubject: {safe_subj}\n{safe_body}\n========================================================\n", flush=True)
            logger.info(f"[EMAIL - CONSOLE] To: {to_email} | Subject: {safe_subj}")
            return {
                "status": "logged",
                "provider": "console",
                "to": to_email,
                "subject": subject,
                "message": "Email logged to console (not actually sent)"
            }
        import asyncio
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    return pool.submit(asyncio.run, self._send(to_email, subject, html_body)).result(timeout=30)
            else:
                return asyncio.run(self._send(to_email, subject, html_body))
        except Exception as e:
            logger.warning(f"Failed to send email via {self.provider} to {to_email}: {e}")
            return {
                "status": "failed",
                "provider": self.provider,
                "to": to_email,
                "error": str(e)
            }

    async def _send_console(self, to_email: str, subject: str, html_body: str) -> dict:
        """Log email to console (development mode)."""
        import sys
        enc = sys.stdout.encoding or "utf-8"
        safe_subj = subject.encode(enc, errors="replace").decode(enc)
        safe_body = html_body.strip().encode(enc, errors="replace").decode(enc)
        logger.info(f"[EMAIL - CONSOLE] To: {to_email}")
        logger.info(f"[EMAIL - CONSOLE] Subject: {safe_subj}")
        print(f"\n==================== [CONSOLE EMAIL] ====================\nTo: {to_email}\nSubject: {safe_subj}\n{safe_body}\n========================================================\n", flush=True)
        return {
            "status": "logged",
            "provider": "console",
            "to": to_email,
            "subject": subject,
            "message": "Email logged to console (not actually sent)"
        }

    async def _send_smtp(self, to_email: str, subject: str, html_body: str) -> dict:
        """Send email via SMTP with STARTTLS on port 587 or SSL on port 465."""
        if not settings.SMTP_HOST:
            raise EmailServiceError(
                "SMTP provider selected but SMTP_HOST is not configured. "
                "Set SMTP_HOST, SMTP_PORT, SMTP_USER, and SMTP_PASSWORD in environment."
            )

        try:
            import aiosmtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            from email.utils import formataddr

            message = MIMEMultipart("alternative")
            sender_name = settings.sender_display_name
            sender_addr = settings.sender_email_address
            message["From"] = formataddr((sender_name, sender_addr)) if sender_name else sender_addr
            message["To"] = to_email
            message["Subject"] = subject
            message.attach(MIMEText(html_body, "html"))

            # Port 587 uses STARTTLS (start_tls=True, use_tls=False)
            # Port 465 uses direct SSL/TLS (use_tls=True, start_tls=False)
            is_starttls = settings.SMTP_PORT == 587
            use_direct_tls = settings.SMTP_PORT == 465

            await aiosmtplib.send(
                message,
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                username=settings.SMTP_USER or None,
                password=settings.smtp_clean_password or settings.SMTP_PASSWORD or None,
                use_tls=use_direct_tls,
                start_tls=is_starttls,
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
