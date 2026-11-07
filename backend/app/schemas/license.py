"""
Pydantic schemas for FSSAI Food License validation, OCR inspection,
and document lifecycle management.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from backend.app.models.enums import LicenseStatus


class LicenseOcrScanResponse(BaseModel):
    extracted_license_number: Optional[str] = None
    extracted_business_name: Optional[str] = None
    extracted_expiry_date: Optional[str] = None
    extracted_issue_date: Optional[str] = None
    is_demo_document: bool = False
    confidence: float = 0.0
    ocr_status: str = "MANUAL_REQUIRED"
    raw_text_snippet: Optional[str] = None
    notice: str = "OCR output is provisional and must be verified by the owner. It does not constitute proof of authenticity."
    file_token: Optional[str] = None  # Temporary upload token or filename for review flow
    original_filename: Optional[str] = None


class KitchenLicenseDocumentResponse(BaseModel):
    id: str
    original_filename: str
    file_size: int
    mime_type: str
    document_type: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KitchenLicenseResponse(BaseModel):
    id: str
    kitchen_id: str
    license_number: str
    raw_license_number: Optional[str] = None
    business_name: str
    issue_date: Optional[datetime] = None
    expiry_date: datetime
    status: LicenseStatus
    verification_source: str = "MANUAL"
    verified_by_user_id: Optional[str] = None
    verified_at: Optional[datetime] = None
    correction_reason: Optional[str] = None
    rejection_reason: Optional[str] = None
    duplicate_flag: bool = False
    duplicate_details: Optional[str] = None
    ocr_extracted_data: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    is_expired: bool = False
    documents: List[KitchenLicenseDocumentResponse] = []

    model_config = ConfigDict(from_attributes=True)


class LicenseSubmissionRequest(BaseModel):
    license_number: str = Field(..., min_length=5, max_length=50, description="14-digit FSSAI License Number")
    business_name: str = Field(..., min_length=2, max_length=200, description="Business name as per FSSAI License")
    expiry_date: str = Field(..., description="Expiration date (YYYY-MM-DD)")
    issue_date: Optional[str] = Field(None, description="Issue date (YYYY-MM-DD)")
    file_token: Optional[str] = Field(None, description="File token from prior OCR scan")


class LicenseVerificationRequest(BaseModel):
    verification_source: str = Field("MANUAL_ADMIN", description="Verification source (MANUAL_ADMIN, OFFICIAL_GOV_PORTAL, etc.)")
    notes: Optional[str] = Field(None, max_length=500, description="Verification evidence or notes")


class LicenseCorrectionRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=500, description="Specific corrections required by owner")
    correction_reason: Optional[str] = Field(None, max_length=500, description="Alias for reason")


class LicenseRejectionRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=500, description="Reason for rejection")
    rejection_reason: Optional[str] = Field(None, max_length=500, description="Alias for reason")


class LicenseRenewalRequest(BaseModel):
    license_number: str = Field(..., min_length=5, max_length=50)
    business_name: str = Field(..., min_length=2, max_length=200)
    expiry_date: str = Field(..., description="New expiration date (YYYY-MM-DD)")
    issue_date: Optional[str] = None
    renewal_notes: Optional[str] = None
