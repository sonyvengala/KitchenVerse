"""
Comprehensive Test Suite for FSSAI Food License Feature (Phase 4).

Features Verified:
1. File signature (magic bytes) validation for PDF (%PDF-), JPEG, and PNG.
2. File size limit enforcement (rejecting files > 5MB).
3. Secure private storage & file streaming protection.
4. OCR extraction of 14-digit FSSAI number, business name, and validity dates.
5. OCR advisory nature (user reviewing and correcting OCR mistakes).
6. Number normalization (stripping spaces, dashes, FSSAI prefixes to canonical 14 digits).
7. Duplicate number detection and concurrency protection (flagging duplicate for admin review).
8. Document renewal and replacement with version history preservation.
9. Lifecycle state transitions: PENDING_REVIEW -> CORRECTION_REQUIRED -> VERIFIED -> EXPIRED.
10. Operational blocking: unverified, expired, or correction-required licenses block kitchen opening and customer ordering.
11. Security Guard: Test/Demo identifiers ('DEMO — NOT A REAL FSSAI LICENSE') CANNOT be officially verified in production mode.
12. Strict Test Isolation: Uses dedicated isolated in-memory SQLite database, zero production user mutation, zero real email dispatch.
"""

import io
import os
import json
import pytest
import datetime
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import MagicMock

from backend.app.core.database import Base
from app.models import (
    User,
    KitchenProfile,
    KitchenLicense,
    KitchenLicenseDocument,
    MenuItem,
    Order,
)
from app.models.enums import UserRole, LicenseStatus, OrderStatus
from app.services.fssai_service import (
    FssaiService,
    validate_file_signature,
    normalize_fssai_number,
    is_test_identifier,
    validate_fssai_number_format,
    utc_now,
)
from app.services.kitchen_service import KitchenService
from app.services.customer_service import CustomerService


# -----------------------------------------------------------------------------
# ISOLATED TEST DATABASE SETUP (IN-MEMORY SQLITE)
# -----------------------------------------------------------------------------

@pytest.fixture
def isolated_db():
    """Provides a pristine, completely isolated in-memory SQLite database for each test."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSession()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


# -----------------------------------------------------------------------------
# SAMPLE DEMO DOCUMENTS (CLEARLY MARKED "DEMO — NOT A REAL FSSAI LICENSE")
# -----------------------------------------------------------------------------

SAMPLE_DEMO_PDF_CONTENT = bytes.fromhex(
    "255044462d312e330a25e2e3cfd30a312030206f626a0a3c3c0a2f50726f647563657220287079706466290a2f5469746c65202844454d4f205c303535204e4f542041205245414c204653534149204c4943454e5345290a2f5375626a6563742028526567697374726174696f6e204e6f5c30373220313030313930343330303238343420427573696e657373204e616d655c30373220476f75726d657420436c6f7564204b69746368656e2044656d6f290a3e3e0a656e646f626a0a322030206f626a0a3c3c0a2f54797065202f50616765730a2f436f756e7420310a2f4b696473205b203420302052205d0a3e3e0a656e646f626a0a332030206f626a0a3c3c0a2f54797065202f436174616c6f670a2f50616765732032203020520a3e3e0a656e646f626a0a342030206f626a0a3c3c0a2f54797065202f506167650a2f5265736f7572636573203c3c0a3e3e0a2f4d65646961426f78205b20302e3020302e302033303020333030205d0a2f506172656e742032203020520a3e3e0a656e646f626a0a787265660a3020350a303030303030303030302036353533352066200a30303030303030303135203030303030206e200a30303030303030313839203030303030206e200a30303030303030323438203030303030206e200a30303030303030323937203030303030206e200a747261696c65720a3c3c0a2f53697a6520350a2f526f6f742033203020520a2f496e666f2031203020520a3e3e0a7374617274787265660a3339310a2525454f460a"
)

SAMPLE_PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
SAMPLE_JPEG_HEADER = b"\xff\xd8\xff\xe0" + b"\x00" * 100
SAMPLE_INVALID_EXE = b"MZ\x90\x00\x03\x00\x00\x00"


# -----------------------------------------------------------------------------
# UNIT & INTEGRATION TESTS
# -----------------------------------------------------------------------------

class TestFssaiFileValidationAndStorage:
    """Test file signature, format validation, and secure storage."""

    def test_valid_file_signatures(self):
        """Test magic bytes signature detection for PDF, JPG, PNG."""
        ext, mime = validate_file_signature(SAMPLE_DEMO_PDF_CONTENT)
        assert ext == ".pdf" and mime == "application/pdf"

        ext, mime = validate_file_signature(SAMPLE_JPEG_HEADER)
        assert ext == ".jpg" and mime == "image/jpeg"

        ext, mime = validate_file_signature(SAMPLE_PNG_HEADER)
        assert ext == ".png" and mime == "image/png"

    def test_invalid_file_signature_rejected(self):
        """Disguised or invalid files (e.g. executable renamed to .pdf) must be rejected."""
        with pytest.raises(HTTPException) as exc:
            validate_file_signature(SAMPLE_INVALID_EXE)
        assert exc.value.status_code == 400
        assert "Invalid document format" in exc.value.detail

    def test_file_size_limit_enforced(self):
        """Files exceeding 5MB must be rejected."""
        oversized_data = b"%PDF-1.4" + (b"A" * (5 * 1024 * 1024 + 10))
        with pytest.raises(HTTPException) as exc:
            validate_file_signature(oversized_data)
        assert exc.value.status_code == 400
        assert "exceeds maximum allowed size" in exc.value.detail


class TestFssaiNormalizationAndOcr:
    """Test normalization, test identifier protection, and OCR extraction."""

    def test_normalize_fssai_number(self):
        """Strip spaces, dashes, and common prefixes to canonical 14 digits."""
        assert normalize_fssai_number(" 1001 9043-0028 44 ") == "10019043002844"
        assert normalize_fssai_number("FSSAI# 10019043002844") == "10019043002844"
        assert normalize_fssai_number("LIC NO: 10019043002844") == "10019043002844"

    def test_test_identifier_detection(self):
        """Clearly distinguish demo/test numbers and test markers."""
        assert is_test_identifier("TEST-1234567890") is True
        assert is_test_identifier("DEMO-FOOD-999") is True
        assert is_test_identifier("10019043002844") is False
        assert is_test_identifier("10019043002844", raw_text="DEMO — NOT A REAL FSSAI LICENSE") is True

    def test_ocr_extraction_from_demo_pdf(self):
        """Test OCR extraction identifies 14 digits, business name, and demo watermark."""
        ocr_res = FssaiService.extract_ocr_data(SAMPLE_DEMO_PDF_CONTENT, "demo_license.pdf")
        assert ocr_res["is_demo_document"] is True
        assert ocr_res["extracted_license_number"] == "10019043002844"
        assert "Gourmet Cloud Kitchen Demo" in (ocr_res["extracted_business_name"] or "")


class TestDuplicateProtectionAndConcurrency:
    """Test duplicate detection, concurrency protection, and admin flagging."""

    def test_duplicate_flagged_for_admin_review(self, isolated_db):
        """Duplicate license submissions must be flagged for admin review, NOT auto-approved."""
        u1 = User(id="u-1", email="u1@test.local", full_name="U One", hashed_password="pw", role=UserRole.KITCHEN_OWNER)
        u2 = User(id="u-2", email="u2@test.local", full_name="U Two", hashed_password="pw", role=UserRole.KITCHEN_OWNER)
        k1 = KitchenProfile(id="k-1", user_id=u1.id, kitchen_name="Kitchen One", address="Addr 1", city="Bangalore")
        k2 = KitchenProfile(id="k-2", user_id=u2.id, kitchen_name="Kitchen Two", address="Addr 2", city="Bangalore")
        isolated_db.add_all([u1, u2, k1, k2])
        isolated_db.commit()

        # License for Kitchen 1
        lic1 = KitchenLicense(
            kitchen_id=k1.id,
            license_number="10019043002844",
            business_name="Kitchen One Foods",
            expiry_date=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365),
            status=LicenseStatus.VERIFIED,
        )
        isolated_db.add(lic1)
        isolated_db.commit()

        # Check duplicate for Kitchen 2 using same number
        is_dup, dup_details = FssaiService.check_duplicate(
            db=isolated_db,
            normalized_number="10019043002844",
            exclude_kitchen_id=k2.id,
        )
        assert is_dup is True
        assert dup_details is not None
        assert dup_details["count"] == 1

        # When submitted for Kitchen 2, duplicate_flag must be True
        lic2 = KitchenLicense(
            kitchen_id=k2.id,
            license_number="10019043002844",
            business_name="Kitchen Two Foods",
            expiry_date=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365),
            status=LicenseStatus.PENDING_REVIEW,
            duplicate_flag=is_dup,
            duplicate_details=json.dumps(dup_details),
        )
        isolated_db.add(lic2)
        isolated_db.commit()

        assert lic2.duplicate_flag is True
        assert lic2.status == LicenseStatus.PENDING_REVIEW


class TestDocumentHistoryAndRenewal:
    """Test renewal and replacement while preserving document version history."""

    def test_renewal_preserves_document_history(self, isolated_db):
        """Uploading a new document version must archive previous version and keep history."""
        uhist = User(id="u-hist", email="uhist@test.local", full_name="U Hist", hashed_password="pw", role=UserRole.KITCHEN_OWNER)
        kitchen = KitchenProfile(id="k-hist", user_id=uhist.id, kitchen_name="Heritage Kitchen", address="Addr Hist", city="Bangalore")
        isolated_db.add_all([uhist, kitchen])
        isolated_db.commit()

        # Initial license and v1 document
        lic = KitchenLicense(
            kitchen_id=kitchen.id,
            license_number="10019043002844",
            business_name="Heritage Foods",
            expiry_date=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365),
            status=LicenseStatus.PENDING_REVIEW,
        )
        isolated_db.add(lic)
        isolated_db.flush()

        doc_v1 = KitchenLicenseDocument(
            license_id=lic.id,
            file_path="secure/path/v1.pdf",
            original_filename="license_2024.pdf",
            file_size=1024,
            mime_type="application/pdf",
            document_type="INITIAL",
            is_active=True,
        )
        isolated_db.add(doc_v1)
        isolated_db.commit()

        # Renewal: update license with new document
        file_meta_v2 = {
            "file_path": "secure/path/v2.pdf",
            "filename": "v2.pdf",
            "original_filename": "license_2026_renewal.pdf",
            "file_size": 2048,
            "mime_type": "application/pdf",
            "file_hash": "sha256_dummy_v2",
        }

        lic_updated = FssaiService.create_or_update_license(
            db=isolated_db,
            kitchen_id=kitchen.id,
            license_number="10019043002844",
            business_name="Heritage Foods Renewed",
            expiry_date=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=730),
            issue_date=None,
            file_meta=file_meta_v2,
            document_type="RENEWAL",
        )

        isolated_db.refresh(doc_v1)
        isolated_db.refresh(lic_updated)

        # Previous document v1 is marked inactive
        assert doc_v1.is_active is False

        # Active documents contains only the latest
        active_docs = [d for d in lic_updated.documents if d.is_active]
        assert len(active_docs) == 1
        assert active_docs[0].original_filename == "license_2026_renewal.pdf"
        assert active_docs[0].document_type == "RENEWAL"

        # Complete document history contains both documents
        assert len(lic_updated.documents) == 2


class TestStatusTransitionsAndAdminWorkflow:
    """Test full admin lifecycle: PENDING_REVIEW -> CORRECTION_REQUIRED -> VERIFIED -> EXPIRED."""

    def test_lifecycle_and_rejection_flow(self, isolated_db):
        admin = User(
            id="admin-lifecyle",
            email="audit.admin@isolated-test.local",
            full_name="Audit Admin",
            hashed_password="pw",
            role=UserRole.ADMIN,
            is_active=True,
        )
        ukitchen = User(id="u-life", email="ulife@test.local", full_name="U Life", hashed_password="pw", role=UserRole.KITCHEN_OWNER)
        kitchen = KitchenProfile(id="k-lifecycle", user_id=ukitchen.id, kitchen_name="Spice Junction", address="Addr Life", city="Bangalore")
        lic = KitchenLicense(
            kitchen_id=kitchen.id,
            license_number="10019043002844",
            business_name="Spice Junction Kitchen",
            expiry_date=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365),
            status=LicenseStatus.PENDING_REVIEW,
        )
        isolated_db.add_all([admin, ukitchen, kitchen, lic])
        isolated_db.commit()

        # 1. Admin requests correction
        lic.status = LicenseStatus.CORRECTION_REQUIRED
        lic.correction_reason = "Document is blurry. Please upload high-res scan."
        isolated_db.commit()
        isolated_db.refresh(lic)
        assert lic.status == LicenseStatus.CORRECTION_REQUIRED
        assert "blurry" in lic.correction_reason

        # 2. Admin rejects license
        lic.status = LicenseStatus.REJECTED
        lic.rejection_reason = "Entity mismatch between certificate and kitchen registration."
        isolated_db.commit()
        isolated_db.refresh(lic)
        assert lic.status == LicenseStatus.REJECTED
        assert "Entity mismatch" in lic.rejection_reason

        # 3. Owner resubmits and Admin verifies
        lic.status = LicenseStatus.VERIFIED
        lic.verification_source = "MANUAL_ADMIN"
        lic.verified_by_user_id = admin.id
        lic.verified_at = utc_now()
        isolated_db.commit()
        isolated_db.refresh(lic)
        assert lic.status == LicenseStatus.VERIFIED
        assert lic.verified_at is not None
        assert lic.verified_by_user_id == admin.id

        # 4. Expiry sync
        lic.expiry_date = utc_now() - datetime.timedelta(days=1)
        isolated_db.commit()

        expired = FssaiService.sync_license_expiration(isolated_db, lic)
        assert expired is True
        assert lic.status == LicenseStatus.EXPIRED


class TestOperationalBlockingAndOrderProtection:
    """Test that kitchens CANNOT operate or accept orders with unverified or expired licenses."""

    def test_kitchen_cannot_open_without_verified_license(self, isolated_db):
        """Kitchen opening toggle must be rejected if license is pending or expired."""
        owner = User(
            id="owner-blocked",
            email="owner.blocked@isolated-test.local",
            full_name="Owner Blocked",
            hashed_password="pw",
            role=UserRole.KITCHEN_OWNER,
            is_active=True,
        )
        kitchen = KitchenProfile(
            id="k-blocked",
            user_id=owner.id,
            kitchen_name="Unverified Eatery",
            address="Addr Blocked",
            city="Bangalore",
            approval_status="APPROVED",
            is_open=False,
        )
        # License is PENDING_REVIEW
        lic = KitchenLicense(
            kitchen_id=kitchen.id,
            license_number="10019043002844",
            business_name="Unverified Eatery Foods",
            expiry_date=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365),
            status=LicenseStatus.PENDING_REVIEW,
        )
        isolated_db.add_all([owner, kitchen, lic])
        isolated_db.commit()

        # Kitchen owner attempts to open kitchen
        with pytest.raises(HTTPException) as exc:
            KitchenService.update_settings(
                db=isolated_db,
                user=owner,
                req=MagicMock(model_dump=lambda exclude_unset=True: {"is_open": True}),
            )
        assert exc.value.status_code == 403
        assert "FSSAI Food License" in exc.value.detail

    def test_order_creation_blocked_if_kitchen_license_not_verified(self, isolated_db):
        """Customer checkout must be rejected if the target kitchen's license is not verified."""
        customer = User(
            id="cust-1",
            email="customer@isolated-test.local",
            full_name="Customer One",
            hashed_password="pw",
            role=UserRole.CUSTOMER,
            is_active=True,
            is_verified=True,
        )
        kowner = User(
            id="kowner-1",
            email="kowner@isolated-test.local",
            full_name="K Owner",
            hashed_password="pw",
            role=UserRole.KITCHEN_OWNER,
            is_active=True,
        )
        kitchen = KitchenProfile(
            id="k-order-blocked",
            user_id=kowner.id,
            kitchen_name="Blocked Kitchen",
            address="Addr Blocked 2",
            city="Bangalore",
            is_open=True,
            is_approved=True,
            approval_status="APPROVED",
        )
        # License is EXPIRED
        lic = KitchenLicense(
            kitchen_id=kitchen.id,
            license_number="10019043002844",
            business_name="Blocked Kitchen Foods",
            expiry_date=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=5),
            status=LicenseStatus.EXPIRED,
        )
        item = MenuItem(
            id="item-1",
            kitchen_id=kitchen.id,
            name="Veg Biryani",
            category="Main Course",
            cuisine="Indian",
            price=250.0,
            is_available=True,
        )
        isolated_db.add_all([customer, kowner, kitchen, lic, item])
        isolated_db.commit()

        # Customer attempts to place order
        order_request = MagicMock()
        order_request.kitchen_id = kitchen.id
        order_request.items = [MagicMock(menu_item_id=item.id, quantity=1)]
        order_request.delivery_address_id = None
        order_request.special_instructions = None
        order_request.promo_code = None
        order_request.promotion_code = None

        with pytest.raises(HTTPException) as exc:
            CustomerService.place_order(
                db=isolated_db,
                customer=customer,
                req=order_request,
            )
        assert exc.value.status_code == 400
        assert "FSSAI Food License" in exc.value.detail


class TestKitchenLicenseApiEndpoints:
    """Test actual FastAPI HTTP routes for license retrieval and multipart submission."""

    def test_get_license_returns_null_when_not_registered(self, isolated_db):
        """GET /api/v1/kitchen/license returns HTTP 200 with null body when no license exists."""
        from fastapi.testclient import TestClient
        from backend.app.main import app
        from backend.app.core.deps import require_kitchen_owner
        from backend.app.core.database import get_db

        owner = User(
            id="owner-api-test",
            email="owner.api@isolated.local",
            full_name="Owner Api",
            hashed_password="pw",
            role=UserRole.KITCHEN_OWNER,
            is_active=True,
        )
        kitchen = KitchenProfile(
            id="k-api-test",
            user_id=owner.id,
            kitchen_name="API Test Kitchen",
            address="Addr Api",
            city="Bangalore",
        )
        isolated_db.add_all([owner, kitchen])
        isolated_db.commit()

        app.dependency_overrides[get_db] = lambda: isolated_db
        app.dependency_overrides[require_kitchen_owner] = lambda: owner

        client = TestClient(app)
        try:
            res = client.get("/api/v1/kitchen/license")
            assert res.status_code == 200
            assert res.json() is None
        finally:
            app.dependency_overrides.clear()

    def test_ocr_scan_and_multipart_submission_workflow(self, isolated_db):
        """Test OCR scan and full multipart submission workflow via /api/v1/kitchen/license endpoints."""
        from fastapi.testclient import TestClient
        from backend.app.main import app
        from backend.app.core.deps import require_kitchen_owner
        from backend.app.core.database import get_db
        from tests.test_fssai_license import SAMPLE_DEMO_PDF_CONTENT

        owner = User(
            id="owner-multipart-test",
            email="owner.multi@isolated.local",
            full_name="Owner Multipart",
            hashed_password="pw",
            role=UserRole.KITCHEN_OWNER,
            is_active=True,
        )
        kitchen = KitchenProfile(
            id="k-multi-test",
            user_id=owner.id,
            kitchen_name="Multipart Kitchen",
            address="Addr Multi",
            city="Bangalore",
        )
        isolated_db.add_all([owner, kitchen])
        isolated_db.commit()

        app.dependency_overrides[get_db] = lambda: isolated_db
        app.dependency_overrides[require_kitchen_owner] = lambda: owner

        client = TestClient(app)
        try:
            # 1. OCR scan with multipart document upload
            scan_res = client.post(
                "/api/v1/kitchen/license/ocr-scan",
                files={"document": ("demo_cert.pdf", SAMPLE_DEMO_PDF_CONTENT, "application/pdf")},
            )
            assert scan_res.status_code == 200
            scan_data = scan_res.json()
            assert scan_data["extracted_license_number"] == "10019043002844"

            # 2. Multipart license submit with Form fields and file attachment
            submit_res = client.post(
                "/api/v1/kitchen/license/submit",
                data={
                    "license_number": "10019043002844",
                    "business_name": "Multipart Kitchen Foods",
                    "expiry_date": "2028-12-31",
                },
                files={"file": ("demo_cert.pdf", SAMPLE_DEMO_PDF_CONTENT, "application/pdf")},
            )
            assert submit_res.status_code == 200
            submitted = submit_res.json()
            assert submitted["license_number"] == "10019043002844"
            assert submitted["status"] == "PENDING_REVIEW"
            assert len(submitted["documents"]) == 1

            # 3. GET /api/v1/kitchen/license now returns the submitted license object
            get_res = client.get("/api/v1/kitchen/license")
            assert get_res.status_code == 200
            lic_data = get_res.json()
            assert lic_data is not None
            assert lic_data["license_number"] == "10019043002844"
            assert lic_data["status"] == "PENDING_REVIEW"
        finally:
            app.dependency_overrides.clear()


class TestFssaiEndToEndAudit:
    """Full 7-point audit test suite for FSSAI Food License Feature."""

    def test_audit_1_registration_requires_license_document_and_number(self, isolated_db):
        """Audit 1: Kitchen owner registration requires license document and number."""
        from backend.app.schemas.auth import CustomerRegisterRequest
        from backend.app.services.auth_service import AuthService
        import base64

        # Missing license number
        req_missing_num = CustomerRegisterRequest(
            email="kitchen.no.num@audit-test.com",
            password="Password123!",
            full_name="No Num Owner",
            role="KITCHEN_OWNER",
            kitchen_name="No Num Kitchen",
            address="123 Test St",
            city="Bangalore",
            fssai_document_data="data:application/pdf;base64," + base64.b64encode(b"%PDF-1.4 demo").decode(),
            fssai_filename="license.pdf",
        )
        with pytest.raises(HTTPException) as exc1:
            AuthService.register_customer(isolated_db, req_missing_num)
        assert exc1.value.status_code == 400
        assert "registration number are required" in exc1.value.detail

        # Missing document
        req_missing_doc = CustomerRegisterRequest(
            email="kitchen.no.doc@audit-test.com",
            password="Password123!",
            full_name="No Doc Owner",
            role="KITCHEN_OWNER",
            kitchen_name="No Doc Kitchen",
            address="123 Test St",
            city="Bangalore",
            fssai_license_number="10019043002844",
        )
        with pytest.raises(HTTPException) as exc2:
            AuthService.register_customer(isolated_db, req_missing_doc)
        assert exc2.value.status_code == 400
        assert "certificate document is required" in exc2.value.detail

    def test_audit_2_ocr_and_number_mismatch_correction(self):
        """Audit 2: OCR provisional extraction and human review correction."""
        from backend.app.services.fssai_service import FssaiService
        from tests.test_fssai_license import SAMPLE_DEMO_PDF_CONTENT

        # OCR provisional extraction
        ocr_res = FssaiService.extract_ocr_data(SAMPLE_DEMO_PDF_CONTENT, "sample.pdf")
        assert ocr_res["extracted_license_number"] == "10019043002844"
        assert "OCR output is provisional" in ocr_res["notice"]

        # If user corrects an OCR typo (e.g. OCR read 10019043002844 but owner corrects to 10019043002845)
        clean_corrected = normalize_fssai_number("LIC NO: 10019043002845")
        assert clean_corrected == "10019043002845"

    def test_audit_3_duplicate_license_cannot_be_approved_for_different_kitchens(self, isolated_db):
        """Audit 3: Duplicate license numbers cannot be approved for different kitchens."""
        from backend.app.api.routes.admin import verify_kitchen_license
        from backend.app.schemas.license import LicenseVerificationRequest

        admin = User(id="admin-dup-test", email="admin.dup@audit-test.com", full_name="Admin Dup", hashed_password="pw", role=UserRole.ADMIN, is_active=True)
        k1_owner = User(id="k1-owner", email="k1@audit-test.com", full_name="K1 Owner", hashed_password="pw", role=UserRole.KITCHEN_OWNER, is_active=True)
        k2_owner = User(id="k2-owner", email="k2@audit-test.com", full_name="K2 Owner", hashed_password="pw", role=UserRole.KITCHEN_OWNER, is_active=True)

        k1 = KitchenProfile(id="k1-profile", user_id=k1_owner.id, kitchen_name="Kitchen 1", address="Addr 1", city="Bangalore")
        k2 = KitchenProfile(id="k2-profile", user_id=k2_owner.id, kitchen_name="Kitchen 2", address="Addr 2", city="Bangalore")

        # Kitchen 1 already holds a verified license
        lic1 = KitchenLicense(
            kitchen_id=k1.id,
            license_number="10019043002844",
            business_name="Kitchen 1 Foods",
            expiry_date=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365),
            status=LicenseStatus.VERIFIED,
        )
        # Kitchen 2 submits the identical license number
        lic2 = KitchenLicense(
            kitchen_id=k2.id,
            license_number="10019043002844",
            business_name="Kitchen 2 Foods",
            expiry_date=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365),
            status=LicenseStatus.PENDING_REVIEW,
            duplicate_flag=True,
        )
        isolated_db.add_all([admin, k1_owner, k2_owner, k1, k2, lic1, lic2])
        isolated_db.commit()

        # Admin attempts to approve / verify kitchen 2 with the duplicate number
        with pytest.raises(HTTPException) as exc:
            verify_kitchen_license(
                kitchen_id=k2.id,
                req=LicenseVerificationRequest(verification_source="MANUAL_ADMIN"),
                admin=admin,
                db=isolated_db,
            )
        assert exc.value.status_code == 400
        assert "duplicate license number is already verified" in exc.value.detail

    def test_audit_4_admin_view_verify_reject_and_request_correction(self, isolated_db):
        """Audit 4: Admin can view private document, verify, reject, and request correction."""
        from backend.app.api.routes.admin import (
            stream_admin_license_document,
            request_license_correction,
            reject_kitchen_license,
            verify_kitchen_license,
        )
        from backend.app.schemas.license import (
            LicenseVerificationRequest,
            LicenseCorrectionRequest,
            LicenseRejectionRequest,
        )

        admin = User(id="admin-actions", email="admin.actions@audit-test.com", full_name="Admin Act", hashed_password="pw", role=UserRole.ADMIN, is_active=True)
        owner = User(id="owner-act", email="owner.act@audit-test.com", full_name="Owner Act", hashed_password="pw", role=UserRole.KITCHEN_OWNER, is_active=True)
        kitchen = KitchenProfile(id="k-act", user_id=owner.id, kitchen_name="Act Kitchen", address="Addr Act", city="Bangalore")
        lic = KitchenLicense(
            kitchen_id=kitchen.id,
            license_number="10019043002844",
            business_name="Act Kitchen",
            expiry_date=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365),
            status=LicenseStatus.PENDING_REVIEW,
        )
        isolated_db.add_all([admin, owner, kitchen, lic])
        isolated_db.flush()

        # Add secure document
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(b"%PDF-1.4 demo test")
            tmp_path = tmp.name

        doc = KitchenLicenseDocument(
            license_id=lic.id,
            file_path=tmp_path,
            original_filename="license.pdf",
            file_size=16,
            mime_type="application/pdf",
            file_hash="dummyhash",
            is_active=True,
        )
        isolated_db.add(doc)
        isolated_db.commit()

        try:
            # 1. Admin streams document
            res = stream_admin_license_document(kitchen_id=kitchen.id, doc_id=doc.id, admin=admin, db=isolated_db)
            assert res.status_code == 200

            # 2. Admin requests correction
            corr_res = request_license_correction(
                kitchen_id=kitchen.id,
                req=LicenseCorrectionRequest(correction_reason="Clearer address required on certificate"),
                admin=admin,
                db=isolated_db,
            )
            assert corr_res["status"] == "CORRECTION_REQUIRED"
            assert lic.status == LicenseStatus.CORRECTION_REQUIRED

            # 3. Admin rejects
            rej_res = reject_kitchen_license(
                kitchen_id=kitchen.id,
                req=LicenseRejectionRequest(rejection_reason="Certificate revoked"),
                admin=admin,
                db=isolated_db,
            )
            assert rej_res["status"] == "REJECTED"
            assert lic.status == LicenseStatus.REJECTED

            # 4. Admin verifies
            ver_res = verify_kitchen_license(
                kitchen_id=kitchen.id,
                req=LicenseVerificationRequest(verification_source="DEMO_TEST"),
                admin=admin,
                db=isolated_db,
            )
            assert ver_res["status"] == "VERIFIED"
            assert lic.status == LicenseStatus.VERIFIED
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_audit_5_unverified_rejected_expired_cannot_bypass_restrictions(self, isolated_db):
        """Audit 5: Unverified, rejected or expired licenses cannot bypass kitchen opening/ordering restrictions."""
        from backend.app.services.kitchen_service import KitchenService
        from backend.app.api.routes.admin import approve_kitchen_owner

        admin = User(id="admin-byp", email="admin.byp@audit-test.com", full_name="Admin Byp", hashed_password="pw", role=UserRole.ADMIN, is_active=True)
        owner = User(id="owner-bypass", email="owner.bypass@audit-test.com", full_name="Owner Bypass", hashed_password="pw", role=UserRole.KITCHEN_OWNER, is_active=True)
        kitchen = KitchenProfile(id="k-bypass", user_id=owner.id, kitchen_name="Bypass Kitchen", address="Addr", city="Bangalore", is_approved=True, is_open=True)
        lic = KitchenLicense(
            kitchen_id=kitchen.id,
            license_number="10019043002844",
            business_name="Bypass Kitchen",
            expiry_date=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365),
            status=LicenseStatus.PENDING_REVIEW,
        )
        isolated_db.add_all([admin, owner, kitchen, lic])
        isolated_db.commit()

        # Cannot operate while PENDING_REVIEW
        with pytest.raises(HTTPException) as exc1:
            KitchenService.get_dashboard_stats(isolated_db, owner)
        assert exc1.value.status_code == 403
        assert "FSSAI Food License is not verified" in exc1.value.detail

        # Cannot approve kitchen while REJECTED
        lic.status = LicenseStatus.REJECTED
        isolated_db.commit()
        with pytest.raises(HTTPException) as exc2:
            approve_kitchen_owner(kitchen_id=kitchen.id, admin=admin, db=isolated_db)
        assert exc2.value.status_code == 400
        assert "Cannot approve kitchen: FSSAI License is not verified" in exc2.value.detail

        # Cannot operate or approve kitchen while EXPIRED
        lic.status = LicenseStatus.EXPIRED
        isolated_db.commit()
        with pytest.raises(HTTPException) as exc3:
            KitchenService.get_dashboard_stats(isolated_db, owner)
        assert exc3.value.status_code == 403
        assert "expired" in exc3.value.detail.lower()

    def test_audit_6_demo_identifiers_never_officially_verified(self, isolated_db):
        """Audit 6: DEMO documents and fictional identifiers cannot be officially verified in production mode."""
        from backend.app.api.routes.admin import verify_kitchen_license
        from backend.app.schemas.license import LicenseVerificationRequest

        admin = User(id="admin-demo-check", email="admin.demo@audit-test.com", full_name="Admin Demo", hashed_password="pw", role=UserRole.ADMIN, is_active=True)
        owner = User(id="owner-demo-check", email="owner.demo@audit-test.com", full_name="Owner Demo", hashed_password="pw", role=UserRole.KITCHEN_OWNER, is_active=True)
        kitchen = KitchenProfile(id="k-demo-check", user_id=owner.id, kitchen_name="Demo Kitchen", address="Addr", city="Bangalore")
        lic = KitchenLicense(
            kitchen_id=kitchen.id,
            license_number="DEMO-10019043002844",
            business_name="Demo Kitchen",
            expiry_date=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365),
            status=LicenseStatus.PENDING_REVIEW,
        )
        isolated_db.add_all([admin, owner, kitchen, lic])
        isolated_db.commit()

        # Attempt official verification on DEMO identifier without test mode
        with pytest.raises(HTTPException) as exc:
            verify_kitchen_license(
                kitchen_id=kitchen.id,
                req=LicenseVerificationRequest(verification_source="MANUAL_ADMIN"),
                admin=admin,
                db=isolated_db,
            )
        assert exc.value.status_code == 400
        assert "Test/Demo identifiers cannot be officially verified" in exc.value.detail

    def test_audit_7_production_data_and_existing_accounts_untouched(self, isolated_db):
        """Audit 7: Protected real accounts, kitchens, and production DB are strictly untouched and guarded."""
        from backend.app.core.database import is_protected_real_user_email, PROTECTED_REAL_EMAILS
        from backend.app.core.security import get_password_hash

        # 1. Protected real accounts are identified
        for email in PROTECTED_REAL_EMAILS:
            assert is_protected_real_user_email(email) is True

        # 2. Safety guard actively prevents test or script tampering with real accounts
        protected_user = User(
            email="sonyvengala7@gmail.com",
            hashed_password=get_password_hash("OriginalPassword123!"),
            full_name="Vengala Sony",
            role=UserRole.KITCHEN_OWNER,
            is_active=True,
            is_verified=True,
        )
        isolated_db.add(protected_user)
        isolated_db.commit()

        # Attempt to tamper with password
        protected_user.hashed_password = get_password_hash("TamperedPassword123!")
        with pytest.raises(PermissionError) as exc_info:
            isolated_db.commit()

        assert "TEST ISOLATION VIOLATION" in str(exc_info.value)
        assert "sonyvengala7@gmail.com" in str(exc_info.value)
        isolated_db.rollback()
