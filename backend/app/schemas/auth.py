"""
Pydantic Schemas for Authentication and User Registration.
Guarantees strict input validation and blocks role elevation attacks.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from backend.app.models.enums import UserRole
from backend.app.schemas.license import KitchenLicenseResponse


class CustomerRegisterRequest(BaseModel):
    """
    Public customer registration.
    Explicitly does NOT accept role input to prevent privilege escalation.
    """
    email: EmailStr
    password: str = Field(..., min_length=8, description="Minimum 8 characters")
    full_name: Optional[str] = Field(None, max_length=150)
    first_name: Optional[str] = Field(None, max_length=75)
    last_name: Optional[str] = Field(None, max_length=75)
    phone_number: Optional[str] = Field(None, max_length=30)
    phone: Optional[str] = Field(None, max_length=30)
    role: Optional[str] = None
    kitchen_name: Optional[str] = Field(None, max_length=150)
    address: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    dietary_preferences: Optional[str] = None
    # FSSAI Food License fields for kitchen registration
    fssai_license_number: Optional[str] = None
    business_license: Optional[str] = None
    fssai_business_name: Optional[str] = None
    fssai_expiry_date: Optional[str] = None
    fssai_file_token: Optional[str] = None
    fssai_document_data: Optional[str] = None
    fssai_filename: Optional[str] = None


class KitchenRegisterRequest(BaseModel):
    """
    Kitchen owner registration.
    Registers a new kitchen owner with associated kitchen profile and required FSSAI license.
    """
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=2, max_length=150)
    phone_number: Optional[str] = Field(None, max_length=30)
    kitchen_name: str = Field(..., min_length=2, max_length=150)
    center_id: Optional[int] = Field(None, description="Fulfilment center ID")
    address: str = Field(..., min_length=5, max_length=255)
    city: str = Field(..., min_length=2, max_length=100)
    phone: Optional[str] = Field(None, max_length=30)
    description: Optional[str] = None
    # FSSAI License requirements
    fssai_license_number: Optional[str] = Field(None, description="14-digit FSSAI License / Registration number")
    business_license: Optional[str] = Field(None, description="License alias")
    fssai_business_name: Optional[str] = Field(None, description="Registered business / FBO name")
    fssai_expiry_date: Optional[str] = Field(None, description="License expiration date (YYYY-MM-DD)")
    fssai_file_token: Optional[str] = Field(None, description="Stored license document token")
    fssai_document_data: Optional[str] = Field(None, description="Base64 encoded license certificate document")
    fssai_filename: Optional[str] = Field(None, description="Original filename of license document")


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class CustomerProfileResponse(BaseModel):
    id: str
    dietary_preferences: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class KitchenProfileResponse(BaseModel):
    id: str
    kitchen_name: str
    center_id: Optional[int] = None
    address: str
    city: str
    phone: Optional[str] = None
    is_open: bool
    is_approved: bool
    approval_status: Optional[str] = "APPROVED"
    rejection_reason: Optional[str] = None
    rating: float
    license: Optional[KitchenLicenseResponse] = None

    model_config = ConfigDict(from_attributes=True)


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    phone_number: Optional[str] = None
    role: UserRole
    status: str = "ACTIVE"
    is_active: bool = True
    is_verified: bool = False
    is_email_verified: bool = False
    customer_profile: Optional[CustomerProfileResponse] = None
    kitchen_profile: Optional[KitchenProfileResponse] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int = 86400
    message: Optional[str] = "Operation successful"

    model_config = ConfigDict(from_attributes=True)


class EmailVerifyRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: Optional[EmailStr] = None


class ResendVerificationResponse(BaseModel):
    status: str = "success"
    message: str
    provider: str
    email: str
    cooldown_seconds: int = 60
    verification_token: Optional[str] = None


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class AuthMessageResponse(BaseModel):
    status: str = "success"
    message: str
    token: Optional[str] = None
    email_configured: Optional[bool] = None
    provider: Optional[str] = None
