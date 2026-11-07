"""
Authentication API Endpoints.
Provides session-based login with secure HttpOnly cookies, real logout,
email verification, password resets, and RBAC profile retrieval.
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.deps import get_current_user, get_current_session, get_session_token_from_request
from backend.app.core.session import create_user_session, revoke_session
from backend.app.models.enums import UserRole
from backend.app.models.user import User, UserSession
from backend.app.schemas.auth import (
    CustomerRegisterRequest,
    KitchenRegisterRequest,
    UserLoginRequest,
    UserResponse,
    EmailVerifyRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    ChangePasswordRequest,
    AuthMessageResponse,
    ResendVerificationRequest,
    ResendVerificationResponse,
)
from backend.app.services.auth_service import AuthService
from backend.app.core.email import email_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def set_session_cookie(response: Response, session_id: str) -> None:
    """Set the HttpOnly session cookie on the response."""
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=session_id,
        max_age=settings.SESSION_MAX_AGE_SECONDS,
        httponly=settings.SESSION_COOKIE_HTTPONLY,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
        path="/",
    )


def _build_user_response(user: User, session: Optional[UserSession] = None, message: str = "Operation successful") -> UserResponse:
    names = (user.full_name or "").split(" ", 1)
    first = names[0] if names else ""
    last = names[1] if len(names) > 1 else ""
    status_str = "PENDING_VERIFICATION" if not user.is_verified else ("ACTIVE" if user.is_active else "INACTIVE")
    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name or "",
        first_name=first,
        last_name=last,
        phone=user.phone_number,
        phone_number=user.phone_number,
        role=user.role,
        status=status_str,
        is_active=user.is_active,
        is_verified=user.is_verified,
        is_email_verified=user.is_verified,
        customer_profile=user.customer_profile,
        kitchen_profile=user.kitchen_profile,
        created_at=user.created_at,
        updated_at=getattr(user, "updated_at", None),
        access_token=session.session_id if session else None,
        refresh_token=session.session_id if session else None,
        token_type="bearer",
        expires_in=settings.SESSION_MAX_AGE_SECONDS,
        message=message,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_customer(
    req: CustomerRegisterRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db)
):
    """Register a new customer or kitchen owner account."""
    user, verification_token = AuthService.register_customer(db, req)
    verification_url = f"{settings.FRONTEND_URL}/verify-email?token={verification_token}"
    try:
        email_service.send_verification_email_sync(user.email, verification_url)
    except Exception as e:
        logger.warning(f"Failed to send customer verification email to {user.email}: {e}")
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    session = create_user_session(db, user.id, ip_address=client_ip, user_agent=user_agent)
    set_session_cookie(response, session.session_id)
    msg = "Kitchen registration successful. Awaiting admin approval." if user.role in (UserRole.KITCHEN_OWNER, "KITCHEN_OWNER") else "Registration successful. Please verify your email."
    return _build_user_response(user, session, msg)


@router.post("/register-kitchen", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_kitchen(
    req: KitchenRegisterRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db)
):
    """Register a new kitchen owner and kitchen profile."""
    user, verification_token = AuthService.register_kitchen(db, req)
    verification_url = f"{settings.FRONTEND_URL}/verify-email?token={verification_token}"
    try:
        email_service.send_verification_email_sync(user.email, verification_url)
    except Exception as e:
        logger.warning(f"Failed to send kitchen verification email to {user.email}: {e}")
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    session = create_user_session(db, user.id, ip_address=client_ip, user_agent=user_agent)
    set_session_cookie(response, session.session_id)
    return _build_user_response(user, session, "Kitchen registration successful. Awaiting admin approval.")


@router.post("/login", response_model=UserResponse)
def login(
    req: UserLoginRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db)
):
    """Authenticate and create a server-side session with HttpOnly cookie."""
    user = AuthService.authenticate_user(db, req.email, req.password)
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    session = create_user_session(db, user.id, ip_address=client_ip, user_agent=user_agent)
    set_session_cookie(response, session.session_id)
    return _build_user_response(user, session, "Login successful")


@router.post("/logout", response_model=AuthMessageResponse)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Perform real server-side session invalidation.
    Invalidates session in the database and clears the HttpOnly cookie.
    """
    session_id = get_session_token_from_request(request)
    if session_id:
        revoke_session(db, session_id)

    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
        httponly=settings.SESSION_COOKIE_HTTPONLY,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )
    return AuthMessageResponse(message="Successfully logged out")


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    session: UserSession = Depends(get_current_session),
):
    """Retrieve current authenticated user profile and active role."""
    return _build_user_response(current_user, session=session, message="Profile retrieved")


@router.post("/verify-email", response_model=AuthMessageResponse)
def verify_email(
    req: EmailVerifyRequest,
    db: Session = Depends(get_db)
):
    """Verify email address with verification token."""
    AuthService.verify_email(db, req.token)
    return AuthMessageResponse(message="Email successfully verified")


@router.post("/resend-verification", response_model=ResendVerificationResponse)
def resend_verification(
    request: Request,
    req: Optional[ResendVerificationRequest] = None,
    db: Session = Depends(get_db)
):
    """
    Resend verification email.
    Supports authenticated sessions and email payload.
    Enforces 60-second cooldown rate limit.
    """
    current_user = None
    session_id = get_session_token_from_request(request)
    if session_id:
        from backend.app.core.session import get_user_from_session
        current_user = get_user_from_session(db, session_id)

    target_email = req.email if req else None
    res = AuthService.resend_verification_email(
        db, target_email=target_email, authenticated_user=current_user
    )
    return ResendVerificationResponse(**res)


@router.post("/forgot-password", response_model=AuthMessageResponse)
def forgot_password(
    req: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Request a password reset.

    Always returns the same outer message (to prevent account enumeration).
    The response message field clarifies whether email was actually delivered.
    The reset token is NEVER returned in the response body.
    """
    token = AuthService.request_password_reset(db, req.email)
    email_delivery_status = "not_applicable"

    if token:
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        try:
            send_result = email_service.send_password_reset_email_sync(req.email, reset_url)
            email_delivery_status = send_result.get("status", "unknown")
            provider = send_result.get("provider", settings.EMAIL_PROVIDER)
            if provider == "console":
                email_delivery_status = "console"
        except Exception as e:
            logger.warning(f"Failed to send password reset email to {req.email}: {e}")
            email_delivery_status = "failed"

    # Build user-facing message
    if not token:
        message = "If an account with this email exists, a password reset link has been prepared."
    elif email_delivery_status == "console":
        message = (
            "Development console fallback — email was NOT delivered to your inbox. "
            "Email provider is not configured for real delivery. "
            "Please contact your administrator to configure SMTP or SendGrid."
        )
    elif email_delivery_status in ("sent", "queued"):
        message = "A password reset link has been sent to your email address. Please check your inbox."
    elif email_delivery_status == "failed":
        message = (
            "A password reset was prepared but the email could not be delivered. "
            "Please contact support or try again later."
        )
    else:
        message = "If an account with this email exists, a password reset link has been prepared."

    is_configured = email_delivery_status in ("sent", "queued")
    return AuthMessageResponse(
        message=message,
        token=None,  # Never expose reset tokens in HTTP responses
        email_configured=is_configured,
        provider=settings.EMAIL_PROVIDER,
    )



@router.post("/reset-password", response_model=AuthMessageResponse)
def reset_password(
    req: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """Reset password and invalidate all prior sessions."""
    user = AuthService.reset_password(db, req.token, req.new_password)
    try:
        email_service.send_password_reset_confirmed_email_sync(user.email)
    except Exception as e:
        logger.warning(f"Failed to send password reset confirmation email to {user.email}: {e}")
    return AuthMessageResponse(message="Password has been successfully reset. Please log in with your new password.")


@router.post("/change-password", response_model=AuthMessageResponse)
def change_password(
    req: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change password for the current authenticated user."""
    AuthService.change_password(db, current_user, req.current_password, req.new_password)
    return AuthMessageResponse(message="Password successfully changed")
