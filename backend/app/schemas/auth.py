"""Pydantic schemas for authentication and user operations."""
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, field_validator


# =============================================
# AUTH SCHEMAS
# =============================================

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(default="CUSTOMER", pattern="^(CUSTOMER|KITCHEN_OWNER)$")

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        errors = []
        if not any(c.isupper() for c in v):
            errors.append("uppercase letter")
        if not any(c.islower() for c in v):
            errors.append("lowercase letter")
        if not any(c.isdigit() for c in v):
            errors.append("digit")
        if not any(c in "!@#$%^&*()_+-=[]{}|;:',.<>?/~`" for c in v):
            errors.append("special character")
        if errors:
            raise ValueError(f"Password must contain at least one: {', '.join(errors)}")
        return v


class RegisterResponse(BaseModel):
    id: UUID
    email: str
    first_name: str
    last_name: str
    role: str
    status: str
    message: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: UUID
    email: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    role: str
    status: str
    is_email_verified: bool
    email_verified_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class VerifyEmailRequest(BaseModel):
    token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        errors = []
        if not any(c.isupper() for c in v):
            errors.append("uppercase letter")
        if not any(c.islower() for c in v):
            errors.append("lowercase letter")
        if not any(c.isdigit() for c in v):
            errors.append("digit")
        if not any(c in "!@#$%^&*()_+-=[]{}|;:',.<>?/~`" for c in v):
            errors.append("special character")
        if errors:
            raise ValueError(f"Password must contain at least one: {', '.join(errors)}")
        return v


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        errors = []
        if not any(c.isupper() for c in v):
            errors.append("uppercase letter")
        if not any(c.islower() for c in v):
            errors.append("lowercase letter")
        if not any(c.isdigit() for c in v):
            errors.append("digit")
        if not any(c in "!@#$%^&*()_+-=[]{}|;:',.<>?/~`" for c in v):
            errors.append("special character")
        if errors:
            raise ValueError(f"Password must contain at least one: {', '.join(errors)}")
        return v


class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None


class ErrorResponse(BaseModel):
    detail: str
    errors: Optional[List[str]] = None


class EmailStatusResponse(BaseModel):
    message: str
    email_configured: bool
    provider: str
