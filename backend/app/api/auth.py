"""Authentication API routes."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.auth import (
    RegisterRequest,
    RegisterResponse,
    LoginRequest,
    TokenResponse,
    UserResponse,
    VerifyEmailRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    ChangePasswordRequest,
    MessageResponse,
    EmailStatusResponse,
)
from app.services.auth_service import AuthService, AuthServiceError

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Register a new user account.
    
    - Validates password strength (uppercase, lowercase, digit, special char, 8+ chars)
    - Creates user with PENDING_VERIFICATION status
    - Creates role-specific profile (customer or kitchen_owner)
    - Attempts to send verification email
    """
    auth_service = AuthService(db)
    try:
        user, verification_token, email_status = await auth_service.register(
            email=request.email,
            password=request.password,
            first_name=request.first_name,
            last_name=request.last_name,
            role=request.role,
        )
    except AuthServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    message = "Registration successful. Please verify your email."
    if email_status == "not_configured":
        message = "Registration successful. Email service not configured - verification email not sent."
    elif email_status == "failed":
        message = "Registration successful. Failed to send verification email."

    return RegisterResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role.value,
        status=user.status.value,
        message=message,
    )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Authenticate user and return JWT tokens.
    
    - Validates credentials
    - Returns access_token and refresh_token
    - Updates last_login_at timestamp
    """
    auth_service = AuthService(db)
    try:
        tokens = await auth_service.login(
            email=request.email,
            password=request.password,
        )
    except AuthServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    return TokenResponse(**tokens)


@router.post("/logout", response_model=MessageResponse)
async def logout(current_user: User = Depends(get_current_user)):
    """
    Logout the current user.
    
    Note: JWT tokens are stateless. This endpoint acknowledges the logout.
    For full session invalidation, implement token blacklisting in a future phase.
    """
    return MessageResponse(message="Successfully logged out")


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(request: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    """
    Verify user's email address using the verification token.
    
    - Validates the token
    - Marks email as verified
    - Updates user status to ACTIVE
    """
    auth_service = AuthService(db)
    try:
        user = await auth_service.verify_email(request.token)
    except AuthServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    return MessageResponse(message="Email verified successfully")


@router.post("/forgot-password", response_model=EmailStatusResponse)
async def forgot_password(request: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """
    Request a password reset email.
    
    - Always returns success to prevent email enumeration
    - If email exists, sends reset link
    - If email service not configured, returns clear status
    """
    auth_service = AuthService(db)
    reset_token, email_status = await auth_service.forgot_password(request.email)

    email_configured = email_status not in ("not_configured", "failed")

    if email_status == "not_configured":
        return EmailStatusResponse(
            message="If an account with this email exists, a reset link has been prepared. Email service is not configured.",
            email_configured=False,
            provider="none",
        )
    elif email_status == "failed":
        return EmailStatusResponse(
            message="If an account with this email exists, a password reset email was attempted but failed.",
            email_configured=False,
            provider="failed",
        )
    else:
        return EmailStatusResponse(
            message="If an account with this email exists, a password reset email has been sent.",
            email_configured=True,
            provider=email_status,
        )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(request: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """
    Reset password using the reset token.
    
    - Validates the reset token
    - Updates password with new hashed password
    """
    auth_service = AuthService(db)
    try:
        await auth_service.reset_password(request.token, request.new_password)
    except AuthServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    return MessageResponse(message="Password reset successfully")


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Change password for authenticated user.
    
    - Requires current password verification
    - Updates to new password
    """
    auth_service = AuthService(db)
    try:
        await auth_service.change_password(
            current_user, request.current_password, request.new_password
        )
    except AuthServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    return MessageResponse(message="Password changed successfully")


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """
    Get the current authenticated user's profile.
    
    - Requires valid JWT token
    - Returns user information (never returns password hash)
    """
    return current_user
