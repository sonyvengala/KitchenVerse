"""
FSSAI Food License Verification, Secure Storage, OCR Extraction,
Duplicate Protection, and Lifecycle Management Service.
"""
import os
import re
import time
import uuid
import hashlib
import logging
from datetime import datetime, timezone, date
from typing import Optional, Tuple, List, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.models.enums import LicenseStatus
from backend.app.models.license import KitchenLicense, KitchenLicenseDocument
from backend.app.models.user import KitchenProfile, User
from backend.app.models.platform import Notification, AuditLog

logger = logging.getLogger(__name__)

# Secure private upload directory (NOT mounted as public static assets)
SECURE_LICENSES_DIR = os.path.join(os.getcwd(), "data", "secure_uploads", "licenses")
os.makedirs(SECURE_LICENSES_DIR, exist_ok=True)

MAX_LICENSE_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_LICENSE_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
ALLOWED_LICENSE_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
}

DEMO_DOCUMENT_WATERMARK = "DEMO — NOT A REAL FSSAI LICENSE"
DEMO_DOCUMENT_WATERMARK_ALT = "DEMO - NOT A REAL FSSAI LICENSE"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_fssai_number(license_num: Optional[str]) -> str:
    """
    Normalizes an FSSAI License / Registration number.
    Strips whitespace, hyphens, prefixes like 'FSSAI#', 'FSSAI-', 'FSSAI:', 'LIC-', etc.
    Returns canonical uppercase stripped string.
    """
    if not license_num:
        return ""
    clean = license_num.strip().upper()
    # Strip common prefix patterns: FSSAI#, FSSAI-, LIC NO:, REGISTRATION NO:, etc.
    clean = re.sub(r'^(?:(?:FSSAI|LIC(?:ENSE)?|REG(?:ISTRATION)?|NO|NUM(?:BER)?)[\s:.#\-/]*)+', '', clean)
    # Remove any non-alphanumeric characters like spaces, dashes, dots, hash
    clean = re.sub(r'[^A-Z0-9]', '', clean)
    return clean


def is_test_identifier(normalized_num: str, raw_text: Optional[str] = None) -> bool:
    """
    Determines if a license number or document is a fictional test/demo identifier.
    Guarantees test identifiers cannot pass production validation or be marked officially verified.
    """
    if not normalized_num:
        return False
    upper_num = normalized_num.upper()
    if upper_num.startswith("TEST") or upper_num.startswith("DEMO") or "TEST" in upper_num or "DEMO" in upper_num:
        return True
    if raw_text and (DEMO_DOCUMENT_WATERMARK in raw_text or DEMO_DOCUMENT_WATERMARK_ALT in raw_text):
        return True
    return False


def validate_fssai_number_format(normalized_num: str, allow_test_identifiers: bool = False) -> Tuple[bool, str]:
    """
    Validates the structure of an FSSAI License/Registration number.
    In India, genuine FSSAI numbers are 14 numeric digits.
    In testing/isolated environments with allow_test_identifiers=True, fictional test patterns are recognized.
    """
    if not normalized_num:
        return False, "License number is required."

    if is_test_identifier(normalized_num):
        if allow_test_identifiers:
            return True, "Valid test/demo identifier format."
        return False, "Test/Demo identifiers cannot be submitted or verified in production mode."

    # Standard FSSAI format: 14 numeric digits
    if not re.match(r'^\d{14}$', normalized_num):
        return False, "FSSAI License number must be exactly 14 digits."

    # Reject trivial repetitions
    if len(set(normalized_num)) == 1:
        return False, "Invalid FSSAI License number: repetitive dummy digits."

    return True, "Valid FSSAI format."


def validate_file_signature(data: bytes) -> Tuple[str, str]:
    """
    Validates file signatures (magic bytes) for PDF, JPG, and PNG.
    Returns (canonical_extension, mime_type) or raises HTTPException.
    """
    if len(data) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded license document is empty.")

    if len(data) > MAX_LICENSE_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"License document exceeds maximum allowed size of {MAX_LICENSE_FILE_SIZE // (1024 * 1024)} MB."
        )

    # 1. PDF magic bytes: %PDF-
    if len(data) >= 4 and data[:4] == b"%PDF":
        return ".pdf", "application/pdf"

    # 2. JPEG magic bytes: FF D8 FF
    if len(data) >= 3 and data[:3] == b"\xff\xd8\xff":
        return ".jpg", "image/jpeg"

    # 3. PNG magic bytes: \x89PNG\r\n\x1a\n
    if len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png", "image/png"

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid document format. Allowed formats are PDF, JPG, and PNG with genuine file signatures."
    )


class FssaiService:
    @staticmethod
    def save_secure_license_file(
        file_content: bytes,
        original_filename: str,
        content_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validates signatures, size limits, and securely stores the document in private storage.
        """
        canonical_ext, verified_mime = validate_file_signature(file_content)

        # Check declared extension if present
        if original_filename:
            declared_ext = os.path.splitext(original_filename)[1].lower()
            if declared_ext and declared_ext not in ALLOWED_LICENSE_EXTENSIONS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid file extension '{declared_ext}'. Allowed extensions are PDF, JPG, and PNG."
                )

        # Compute SHA-256 hash for document integrity and duplication verification
        file_hash = hashlib.sha256(file_content).hexdigest()

        # Generate secure random filename
        safe_filename = f"license_{int(time.time())}_{uuid.uuid4().hex[:12]}{canonical_ext}"
        filepath = os.path.join(SECURE_LICENSES_DIR, safe_filename)

        with open(filepath, "wb") as f:
            f.write(file_content)

        return {
            "file_path": filepath,
            "filename": safe_filename,
            "original_filename": original_filename or safe_filename,
            "file_size": len(file_content),
            "mime_type": verified_mime,
            "file_hash": file_hash,
        }

    @staticmethod
    def extract_ocr_data(file_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Extracts license number, business name, and validity dates from PDF or image content.
        OCR output is strictly advisory and NEVER treated as proof that a license is genuine.
        """
        raw_text = ""
        is_demo = False
        canonical_ext, _ = validate_file_signature(file_content)

        if canonical_ext == ".pdf":
            try:
                import pypdf
                import io
                reader = pypdf.PdfReader(io.BytesIO(file_content))
                for page in reader.pages:
                    text = page.extract_text() or ""
                    raw_text += text + "\n"
                if reader.metadata:
                    raw_text += " " + " ".join(str(v) for v in reader.metadata.values()) + "\n"
            except Exception as e:
                logger.warning(f"pypdf extraction notice: {e}")
        else:
            # Image formats (JPG/PNG)
            # Try to read text if Pillow has text chunks or embedded metadata, or basic heuristic search
            try:
                from PIL import Image
                import io
                img = Image.open(io.BytesIO(file_content))
                # Check for metadata comments/info
                info_text = str(img.info or "")
                raw_text += info_text + "\n"
            except Exception as e:
                logger.warning(f"Image inspection notice: {e}")

        # Check for DEMO watermark
        if DEMO_DOCUMENT_WATERMARK in raw_text or DEMO_DOCUMENT_WATERMARK_ALT in raw_text:
            is_demo = True

        # 1. Extract FSSAI License / Registration Number
        extracted_license_number = None
        # Pattern A: Explicit label
        lic_match = re.search(
            r'(?:Registration\s*(?:No|Number)|License\s*(?:No|Number)|Licence\s*(?:No|Number)|FSSAI\s*(?:No|Number)?)[^\d\n\r]*([0-9]{14}|TEST-[A-Z0-9-]+)',
            raw_text,
            re.IGNORECASE
        )
        if lic_match:
            extracted_license_number = lic_match.group(1).strip()
        else:
            # Pattern B: Standalone 14 digits
            digit14 = re.search(r'\b([0-9]{14})\b', raw_text)
            if digit14:
                extracted_license_number = digit14.group(1).strip()
            elif is_demo:
                demo_lic = re.search(r'\b(TEST-[A-Z0-9-]+)\b', raw_text)
                if demo_lic:
                    extracted_license_number = demo_lic.group(1).strip()

        # 2. Extract Business / FBO Name
        extracted_business_name = None
        bname_match = re.search(
            r'(?:Name\s+of\s+(?:Food\s+Business\s+Operator|FBO|Applicant)|Business\s+Name|Establishment\s+Name)[:\s.-]+([^\n\r]+)',
            raw_text,
            re.IGNORECASE
        )
        if bname_match:
            extracted_business_name = bname_match.group(1).strip()

        # 3. Extract Expiry Date / Validity Date
        extracted_expiry_date = None
        exp_match = re.search(
            r'(?:Valid\s*(?:Upto|Until|Through)|Validity|Period\s*of\s*Validity|Expiry\s*Date)[:\s.-]*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4}|[0-9]{4}-[0-9]{2}-[0-9]{2})',
            raw_text,
            re.IGNORECASE
        )
        if exp_match:
            extracted_expiry_date = exp_match.group(1).strip()

        # 4. Extract Issue Date
        extracted_issue_date = None
        iss_match = re.search(
            r'(?:Date\s+of\s+Issue|Issued\s+On|Registration\s+Date)[:\s.-]*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4}|[0-9]{4}-[0-9]{2}-[0-9]{2})',
            raw_text,
            re.IGNORECASE
        )
        if iss_match:
            extracted_issue_date = iss_match.group(1).strip()

        # Confidence calculation
        found_fields = sum(1 for f in [extracted_license_number, extracted_business_name, extracted_expiry_date] if f)
        confidence = round(found_fields / 3.0, 2)
        ocr_status = "SUCCESS" if found_fields >= 2 else ("PARTIAL" if found_fields == 1 else "MANUAL_REQUIRED")

        return {
            "extracted_license_number": extracted_license_number,
            "extracted_business_name": extracted_business_name,
            "extracted_expiry_date": extracted_expiry_date,
            "extracted_issue_date": extracted_issue_date,
            "is_demo_document": is_demo,
            "confidence": confidence,
            "ocr_status": ocr_status,
            "raw_text_snippet": raw_text[:500] if raw_text else "",
            "notice": "OCR output is provisional and must be verified by the owner. It does not constitute proof of authenticity.",
        }

    @staticmethod
    def parse_date(date_str: Optional[str]) -> Optional[datetime]:
        """Parse date strings in standard formats (YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY)."""
        if not date_str:
            return None
        date_str = date_str.strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        # Fallback ISO format
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None

    @staticmethod
    def check_duplicate(
        db: Session,
        normalized_number: str,
        exclude_kitchen_id: Optional[str] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Checks for existing kitchen registrations sharing the same normalized FSSAI license number.
        Uses database row locking to prevent race conditions during concurrent submissions.
        """
        if not normalized_number:
            return False, None

        q = db.query(KitchenLicense).filter(KitchenLicense.license_number == normalized_number)
        if exclude_kitchen_id:
            q = q.filter(KitchenLicense.kitchen_id != exclude_kitchen_id)

        # In transactional databases (PostgreSQL/SQLite), inspect existing records
        try:
            conflicting_licenses = q.with_for_update(read=True).all()
        except Exception:
            # Fallback if with_for_update not supported by SQLite connection mode
            conflicting_licenses = q.all()

        if not conflicting_licenses:
            return False, None

        conflicts = []
        for lic in conflicting_licenses:
            kitchen = db.query(KitchenProfile).filter(KitchenProfile.id == lic.kitchen_id).first()
            conflicts.append({
                "kitchen_id": lic.kitchen_id,
                "kitchen_name": kitchen.kitchen_name if kitchen else "Unknown",
                "status": lic.status.value if hasattr(lic.status, "value") else str(lic.status),
                "created_at": lic.created_at.isoformat() if lic.created_at else None,
            })

        return True, {
            "count": len(conflicts),
            "conflicts": conflicts,
            "warning": "Duplicate FSSAI license number detected. Flagged for platform administrator review.",
        }

    @staticmethod
    def create_or_update_license(
        db: Session,
        kitchen_id: str,
        license_number: str,
        business_name: str,
        expiry_date: datetime,
        issue_date: Optional[datetime],
        file_meta: Dict[str, Any],
        ocr_meta: Optional[Dict[str, Any]] = None,
        document_type: str = "INITIAL",
        allow_test_identifiers: bool = False,
    ) -> KitchenLicense:
        """
        Creates or updates a kitchen license, recording document history and duplicate flags.
        """
        import json
        normalized_num = normalize_fssai_number(license_number)
        valid, msg = validate_fssai_number_format(normalized_num, allow_test_identifiers=allow_test_identifiers)
        if not valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

        if expiry_date < utc_now():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="License expiry date cannot be in the past. Please provide a valid active license."
            )

        # Check for duplicates across kitchens
        is_dup, dup_info = FssaiService.check_duplicate(db, normalized_num, exclude_kitchen_id=kitchen_id)

        existing_license = db.query(KitchenLicense).filter(KitchenLicense.kitchen_id == kitchen_id).first()

        if existing_license:
            # Update existing license
            existing_license.raw_license_number = license_number
            existing_license.license_number = normalized_num
            existing_license.business_name = business_name
            existing_license.expiry_date = expiry_date
            if issue_date:
                existing_license.issue_date = issue_date
            existing_license.status = LicenseStatus.PENDING_REVIEW
            existing_license.duplicate_flag = is_dup
            existing_license.duplicate_details = json.dumps(dup_info) if dup_info else None
            if ocr_meta:
                existing_license.ocr_extracted_data = json.dumps(ocr_meta)
            existing_license.updated_at = utc_now()
            license_obj = existing_license

            # Deactivate previous active documents for this license
            db.query(KitchenLicenseDocument).filter(
                KitchenLicenseDocument.license_id == license_obj.id
            ).update({"is_active": False})
        else:
            license_obj = KitchenLicense(
                kitchen_id=kitchen_id,
                license_number=normalized_num,
                raw_license_number=license_number,
                business_name=business_name,
                issue_date=issue_date,
                expiry_date=expiry_date,
                status=LicenseStatus.PENDING_REVIEW,
                verification_source="MANUAL",
                duplicate_flag=is_dup,
                duplicate_details=json.dumps(dup_info) if dup_info else None,
                ocr_extracted_data=json.dumps(ocr_meta) if ocr_meta else None,
            )
            db.add(license_obj)
            db.flush()

        # Add new document to preserve history
        doc = KitchenLicenseDocument(
            license_id=license_obj.id,
            file_path=file_meta["file_path"],
            original_filename=file_meta["original_filename"],
            file_size=file_meta["file_size"],
            mime_type=file_meta["mime_type"],
            file_hash=file_meta.get("file_hash"),
            document_type=document_type,
            ocr_extracted_data=json.dumps(ocr_meta) if ocr_meta else None,
            is_active=True,
        )
        db.add(doc)

        # Update KitchenProfile approval status
        kitchen = db.query(KitchenProfile).filter(KitchenProfile.id == kitchen_id).first()
        if kitchen:
            if kitchen.approval_status != "APPROVED":
                kitchen.approval_status = "PENDING_APPROVAL"
                kitchen.is_approved = False

        db.commit()
        db.refresh(license_obj)
        return license_obj

    @staticmethod
    def sync_license_expiration(db: Session, license: KitchenLicense) -> bool:
        """
        Evaluates whether a license has expired and updates states accordingly.
        """
        if not license.expiry_date:
            return False

        exp_date = license.expiry_date
        if hasattr(exp_date, "tzinfo") and exp_date.tzinfo is None:
            exp_date = exp_date.replace(tzinfo=timezone.utc)

        if exp_date < utc_now():
            if license.status != LicenseStatus.EXPIRED:
                license.status = LicenseStatus.EXPIRED
                license.updated_at = utc_now()
                # Kitchen operations must be immediately halted
                if license.kitchen:
                    license.kitchen.is_open = False
                    license.kitchen.is_approved = False
                    license.kitchen.approval_status = "SUSPENDED"

                db.commit()
                db.refresh(license)
                return True
        return False
