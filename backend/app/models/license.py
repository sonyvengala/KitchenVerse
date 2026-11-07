"""
FSSAI Food License and Document History Models.
Enforces multi-stage verification, document replacement/renewal history,
duplicate tracking, and explicit lifecycle states.
"""
from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, Text, Enum
from sqlalchemy.orm import relationship
from backend.app.core.database import Base
from backend.app.models.enums import LicenseStatus


def utc_now():
    return datetime.now(timezone.utc)


class KitchenLicense(Base):
    __tablename__ = "kitchen_licenses"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    kitchen_id = Column(String(36), ForeignKey("kitchen_profiles.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    license_number = Column(String(50), nullable=False, index=True)  # Normalized 14-digit FSSAI registration/license number
    raw_license_number = Column(String(100), nullable=True)  # Original input before normalization
    business_name = Column(String(200), nullable=False)  # Food Business Operator (FBO) Name
    issue_date = Column(DateTime(timezone=True), nullable=True)
    expiry_date = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(Enum(LicenseStatus), default=LicenseStatus.PENDING_REVIEW, nullable=False, index=True)
    verification_source = Column(String(50), default="MANUAL", nullable=False)  # e.g., MANUAL_ADMIN, DEMO_TEST, OFFICIAL_FSSAI
    verified_by_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    correction_reason = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    duplicate_flag = Column(Boolean, default=False, nullable=False, index=True)
    duplicate_details = Column(Text, nullable=True)  # JSON metadata describing duplicate registrations
    ocr_extracted_data = Column(Text, nullable=True)  # JSON metadata of latest OCR extraction
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    kitchen = relationship("KitchenProfile", back_populates="license")
    documents = relationship(
        "KitchenLicenseDocument",
        back_populates="license",
        cascade="all, delete-orphan",
        order_by="desc(KitchenLicenseDocument.created_at)"
    )
    verified_by = relationship("User", foreign_keys=[verified_by_user_id])


class KitchenLicenseDocument(Base):
    """
    Stores each license file version to preserve complete renewal and replacement history.
    """
    __tablename__ = "kitchen_license_documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    license_id = Column(String(36), ForeignKey("kitchen_licenses.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path = Column(String(255), nullable=False)  # Private filesystem path in data/secure_uploads/licenses/
    original_filename = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)
    file_hash = Column(String(64), nullable=True, index=True)  # SHA-256 digest
    document_type = Column(String(50), default="INITIAL", nullable=False)  # INITIAL, REPLACEMENT, RENEWAL
    ocr_extracted_data = Column(Text, nullable=True)  # JSON metadata extracted from this specific document
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationship
    license = relationship("KitchenLicense", back_populates="documents")
