"""Authentication service - business logic for auth operations."""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    create_email_verification_token,
    create_password_reset_token,
    decode_token,
)
from app.core.email import email_service, EmailServiceError
from app.models.user import User, UserRole, UserStatus, CustomerProfile, KitchenProfile


class AuthServiceError(Exception):
    """Base auth service error."""
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AuthService:
    """Handles all authentication business logic."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(
        self,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        role: str = "CUSTOMER",
    ) -> tuple:
        """
        Register a new user.
        Returns (user, verification_token, email_status).
        """
        # Security: Explicitly reject ADMIN role in public registration
        if role == "ADMIN":
            raise AuthServiceError("ADMIN role cannot be registered publicly", 403)
        
        # Validate role is allowed for public registration
        if role not in ["CUSTOMER", "KITCHEN_OWNER"]:
            raise AuthServiceError(f"Invalid role: {role}", 400)
        
        # Check if email already exists
        result = await self.db.execute(select(User).where(User.email == email.lower()))
        existing_user = result.scalar_one_or_none()
        if existing_user:
            raise AuthServiceError("An account with this email already exists", 409)

        # Create user
        user = User(
            email=email.lower(),
            hashed_password=hash_password(password),
            first_name=first_name,
            last_name=last_name,
            role=UserRole(role),
            status=UserStatus.PENDING_VERIFICATION,
            is_email_verified=False,
        )
        self.db.add(user)
        await self.db.flush()

        # Create role-specific profile
        if role == "CUSTOMER":
            profile = CustomerProfile(user_id=user.id)
            self.db.add(profile)
        elif role == "KITCHEN_OWNER":
            profile = KitchenProfile(user_id=user.id, kitchen_name=f"{first_name}'s Kitchen")
            self.db.add(profile)

        await self.db.flush()

        # Create email verification token
        verification_token = create_email_verification_token(str(user.id))

        # Try to send verification email
        email_status = "not_configured"
        try:
            verification_url = f"{settings.FRONTEND_URL}/verify-email?token={verification_token}"
            result = await email_service.send_verification_email(user.email, verification_url)
            email_status = result.get("provider", "unknown")
        except EmailServiceError:
            email_status = "not_configured"
        except Exception:
            email_status = "failed"

        return user, verification_token, email_status

    async def login(self, email: str, password: str) -> dict:
        """
        Authenticate user and return tokens.
        """
        result = await self.db.execute(select(User).where(User.email == email.lower()))
        user = result.scalar_one_or_none()

        if not user:
            raise AuthServiceError("Invalid email or password", 401)

        if not verify_password(password, user.hashed_password):
            raise AuthServiceError("Invalid email or password", 401)

        if user.status == UserStatus.SUSPENDED:
            raise AuthServiceError("Account is suspended. Contact support.", 403)

        # Update last login
        user.last_login_at = datetime.now(timezone.utc)
        await self.db.flush()

        # Create tokens
        token_data = {"sub": str(user.id), "role": user.role.value}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }

    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def verify_email(self, token: str) -> User:
        """Verify user's email using token."""
        payload = decode_token(token)
        if payload is None:
            raise AuthServiceError("Invalid or expired verification token", 400)

        if payload.get("type") != "email_verification":
            raise AuthServiceError("Invalid token type", 400)

        user_id = payload.get("sub")
        if not user_id:
            raise AuthServiceError("Invalid token payload", 400)

        result = await self.db.execute(select(User).where(User.id == UUID(user_id)))
        user = result.scalar_one_or_none()

        if not user:
            raise AuthServiceError("User not found", 404)

        if user.is_email_verified:
            raise AuthServiceError("Email already verified", 400)

        user.is_email_verified = True
        user.email_verified_at = datetime.now(timezone.utc)
        user.status = UserStatus.ACTIVE
        await self.db.flush()

        return user

    async def forgot_password(self, email: str) -> tuple:
        """
        Initiate password reset.
        Returns (reset_token, email_status).
        Always returns success to prevent email enumeration.
        """
        result = await self.db.execute(select(User).where(User.email == email.lower()))
        user = result.scalar_one_or_none()

        email_status = "not_configured"

        if user:
            reset_token = create_password_reset_token(str(user.id))
            try:
                reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
                result = await email_service.send_password_reset_email(user.email, reset_url)
                email_status = result.get("provider", "unknown")
            except EmailServiceError:
                email_status = "not_configured"
            except Exception:
                email_status = "failed"

        return reset_token if user else None, email_status

    async def reset_password(self, token: str, new_password: str) -> User:
        """Reset user's password using token."""
        payload = decode_token(token)
        if payload is None:
            raise AuthServiceError("Invalid or expired reset token", 400)

        if payload.get("type") != "password_reset":
            raise AuthServiceError("Invalid token type", 400)

        user_id = payload.get("sub")
        if not user_id:
            raise AuthServiceError("Invalid token payload", 400)

        result = await self.db.execute(select(User).where(User.id == UUID(user_id)))
        user = result.scalar_one_or_none()

        if not user:
            raise AuthServiceError("User not found", 404)

        user.hashed_password = hash_password(new_password)
        await self.db.flush()

        return user

    async def change_password(self, user: User, current_password: str, new_password: str) -> User:
        """Change user's password (requires current password)."""
        if not verify_password(current_password, user.hashed_password):
            raise AuthServiceError("Current password is incorrect", 400)

        user.hashed_password = hash_password(new_password)
        await self.db.flush()

        return user
