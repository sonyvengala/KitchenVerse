"""
Comprehensive tests for Kitchen Owner Removal and Legitimate Account Protections:
1. Individual removal of disposable test kitchen records.
2. Safe archival of kitchen records with historical orders/payments.
3. Protected-account deletion prevention (b23it030@kitsw.ac.in & sonyvengala7@gmail.com).
4. Bulk removal with mixed eligible and protected IDs.
5. Unauthorized access prevention (non-admin blocked with HTTP 403).
6. Non-existent ID handling (HTTP 404 for single, error reporting for batch).
7. Orphaned kitchen owner account cleanup without a kitchen profile.
8. Database persistence verification after removal.
"""

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.security import get_password_hash
from backend.app.models.enums import UserRole, OrderStatus, PaymentStatus, LicenseStatus
from backend.app.models.user import User, KitchenProfile
from backend.app.models.order import Order, OrderItem, Payment, Review
from backend.app.models.menu import MenuItem
from backend.app.models.inventory import Inventory
from backend.app.models.license import KitchenLicense, KitchenLicenseDocument
from backend.app.models.platform import AuditLog


def _login_as(client: TestClient, email: str, password: str = "TestPass123!") -> None:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    cookie = resp.cookies.get(settings.SESSION_COOKIE_NAME)
    client.cookies.set(settings.SESSION_COOKIE_NAME, cookie)


def test_unauthorized_access_prevented(client: TestClient, db_session: Session):
    """Non-admin users and unauthenticated requests cannot remove kitchen owners."""
    customer = User(
        email="customer_unauth_test@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Normal Customer",
        role=UserRole.CUSTOMER,
        is_active=True,
        is_verified=True,
    )
    db_session.add(customer)
    db_session.commit()

    random_id = str(uuid.uuid4())

    # 1. Unauthenticated request
    unauth_resp = client.delete(f"/api/v1/admin/kitchen-owners/{random_id}")
    assert unauth_resp.status_code in (401, 403)

    unauth_batch = client.post("/api/v1/admin/kitchen-owners/batch-remove", json={"kitchen_ids": [random_id]})
    assert unauth_batch.status_code in (401, 403)

    # 2. Customer login
    _login_as(client, customer.email)
    cust_resp = client.delete(f"/api/v1/admin/kitchen-owners/{random_id}")
    assert cust_resp.status_code == 403

    cust_batch = client.post("/api/v1/admin/kitchen-owners/batch-remove", json={"kitchen_ids": [random_id]})
    assert cust_batch.status_code == 403


def test_invalid_or_nonexistent_ids(client: TestClient, db_session: Session):
    """Admin receives 404 for single non-existent ID and error feedback in batch mode."""
    admin = User(
        email="admin_nonexistent_test@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Admin Nonexistent",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    db_session.add(admin)
    db_session.commit()

    _login_as(client, admin.email)

    fake_id = str(uuid.uuid4())

    # Single remove of nonexistent ID -> 404
    resp = client.delete(f"/api/v1/admin/kitchen-owners/{fake_id}")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()

    # Batch remove of nonexistent IDs -> returns report with error
    batch_resp = client.post("/api/v1/admin/kitchen-owners/batch-remove", json={"kitchen_ids": [fake_id]})
    assert batch_resp.status_code == 200
    b_data = batch_resp.json()
    assert b_data["deleted_count"] == 0
    assert any("not found" in err.lower() for err in b_data.get("errors", []))


def test_protected_account_individual_removal_prevention(client: TestClient, db_session: Session):
    """The two legitimate verified kitchen owners cannot be removed via individual delete."""
    admin = User(
        email="admin_protect_test@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Admin Protector",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    # Legitimate Owner 1: Rohith Kalli
    rohith = User(
        email="b23it030@kitsw.ac.in",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Rohith Kalli",
        role=UserRole.KITCHEN_OWNER,
        is_active=True,
        is_verified=True,
    )
    # Legitimate Owner 2: Vengala Sony
    sony = User(
        email="sonyvengala7@gmail.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="VENGALA SONY",
        role=UserRole.KITCHEN_OWNER,
        is_active=True,
        is_verified=True,
    )
    db_session.add_all([admin, rohith, sony])
    db_session.commit()

    k_rohith = KitchenProfile(
        user_id=rohith.id,
        kitchen_name="KITS Gourmet Cloud Kitchen",
        address="KITS Campus, Yerragattu Hillock",
        city="Warangal",
        is_approved=True,
        is_open=True,
        approval_status="APPROVED",
    )
    k_sony = KitchenProfile(
        user_id=sony.id,
        kitchen_name="VENGALA SONY's Kitchen",
        address="Kakatiya Nagar",
        city="Hanamkonda",
        is_approved=True,
        is_open=True,
        approval_status="APPROVED",
    )
    db_session.add_all([k_rohith, k_sony])
    db_session.commit()

    _login_as(client, admin.email)

    # Attempt to delete Rohith's kitchen
    resp1 = client.delete(f"/api/v1/admin/kitchen-owners/{k_rohith.id}")
    assert resp1.status_code == 400
    assert "protected legitimate kitchen owner" in resp1.json()["detail"].lower()

    # Attempt to delete Sony's kitchen
    resp2 = client.delete(f"/api/v1/admin/kitchen-owners/{k_sony.id}")
    assert resp2.status_code == 400
    assert "protected legitimate kitchen owner" in resp2.json()["detail"].lower()

    # Verify both records and owners are completely intact in DB
    db_session.refresh(k_rohith)
    db_session.refresh(rohith)
    db_session.refresh(k_sony)
    db_session.refresh(sony)

    assert k_rohith.approval_status == "APPROVED"
    assert rohith.is_active is True
    assert k_sony.approval_status == "APPROVED"
    assert sony.is_active is True


def test_protected_account_bulk_removal_prevention(client: TestClient, db_session: Session):
    """Bulk removal skips and protects legitimate owners while cleaning eligible test records."""
    admin = User(
        email="admin_bulk_protect@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Admin Bulk Guard",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    # Protected legitimate owner
    rohith = User(
        email="b23it030@kitsw.ac.in",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Rohith Kalli",
        role=UserRole.KITCHEN_OWNER,
        is_active=True,
        is_verified=True,
    )
    # Disposable synthetic test owner
    test_owner = User(
        email="master_chef_999@cloudkitchen.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Master Chef Disposable",
        role=UserRole.KITCHEN_OWNER,
        is_active=False,
        is_verified=False,
    )
    db_session.add_all([admin, rohith, test_owner])
    db_session.commit()

    k_rohith = KitchenProfile(
        user_id=rohith.id,
        kitchen_name="KITS Gourmet Cloud Kitchen",
        address="KITS Campus, Yerragattu Hillock",
        city="Warangal",
        is_approved=True,
        is_open=True,
        approval_status="APPROVED",
    )
    k_test = KitchenProfile(
        user_id=test_owner.id,
        kitchen_name="Chef Delight Disposable Test",
        address="44 Test Avenue",
        city="Warangal",
        is_approved=False,
        is_open=False,
        approval_status="PENDING",
    )
    db_session.add_all([k_rohith, k_test])
    db_session.commit()

    _login_as(client, admin.email)

    resp = client.post(
        "/api/v1/admin/kitchen-owners/batch-remove",
        json={"kitchen_ids": [k_rohith.id, k_test.id]}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["deleted_count"] == 1
    assert data["archived_count"] == 0
    # Protected owner was rejected with error explanation
    assert any("protected" in err.lower() for err in data.get("errors", []))

    # Rohith remains intact
    assert db_session.query(KitchenProfile).filter(KitchenProfile.id == k_rohith.id).first() is not None
    assert db_session.query(User).filter(User.id == rohith.id).first() is not None

    # Test record permanently removed
    assert db_session.query(KitchenProfile).filter(KitchenProfile.id == k_test.id).first() is None
    assert db_session.query(User).filter(User.id == test_owner.id).first() is None


def test_individual_removal_clean_test_record_with_dependent_data(client: TestClient, db_session: Session):
    """Disposable test kitchen with menu items, licenses, and inventory is completely wiped."""
    admin = User(
        email="admin_clean_test@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Admin Cleaner",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    test_owner = User(
        email="disposable_chef_888@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Master Chef 888",
        role=UserRole.KITCHEN_OWNER,
        is_active=False,
        is_verified=False,
    )
    db_session.add_all([admin, test_owner])
    db_session.commit()

    kitchen = KitchenProfile(
        user_id=test_owner.id,
        kitchen_name="Chef Delight Test 888",
        address="888 Test Kitchen Lane",
        city="Warangal",
        is_approved=False,
        is_open=False,
        approval_status="PENDING",
    )
    db_session.add(kitchen)
    db_session.commit()

    # Add menu item
    menu_item = MenuItem(
        kitchen_id=kitchen.id,
        name="Test Paneer Butter Masala",
        category="Main Course",
        cuisine="North Indian",
        price=180.0,
        is_available=True,
    )
    import datetime
    # Add food license & document
    lic = KitchenLicense(
        kitchen_id=kitchen.id,
        license_number="10019043002888",
        business_name="Chef Delight Test 888",
        status=LicenseStatus.PENDING_REVIEW,
        expiry_date=datetime.date.today() + datetime.timedelta(days=365),
    )
    db_session.add_all([menu_item, lic])
    db_session.commit()

    lic_doc = KitchenLicenseDocument(
        license_id=lic.id,
        original_filename="sample_license.pdf",
        file_path="uploads/licenses/stored_888.pdf",
        file_size=1024,
        mime_type="application/pdf",
        is_active=True,
    )
    from backend.app.models.menu import Ingredient
    ing = Ingredient(
        kitchen_id=kitchen.id,
        name="Test Butter",
        unit="kg",
        current_stock=10.0,
    )
    db_session.add(ing)
    db_session.commit()

    inv = Inventory(
        kitchen_id=kitchen.id,
        ingredient_id=ing.id,
        quantity=10.0,
        unit="kg",
    )
    db_session.add_all([lic_doc, inv])
    db_session.commit()

    k_id = kitchen.id
    u_id = test_owner.id
    lic_id = lic.id

    _login_as(client, admin.email)

    resp = client.delete(f"/api/v1/admin/kitchen-owners/{k_id}")
    assert resp.status_code == 200
    assert resp.json()["action"] in ("deleted", "removed")

    # Database persistence verification: All dependent and parent records removed
    assert db_session.query(KitchenProfile).filter(KitchenProfile.id == k_id).first() is None
    assert db_session.query(User).filter(User.id == u_id).first() is None
    assert db_session.query(MenuItem).filter(MenuItem.kitchen_id == k_id).first() is None
    assert db_session.query(KitchenLicense).filter(KitchenLicense.id == lic_id).first() is None
    assert db_session.query(KitchenLicenseDocument).filter(KitchenLicenseDocument.license_id == lic_id).first() is None
    assert db_session.query(Inventory).filter(Inventory.kitchen_id == k_id).first() is None


def test_removal_with_historical_orders_is_safely_archived(client: TestClient, db_session: Session):
    """Kitchen with historical customer orders and payments is archived, not hard-deleted."""
    admin = User(
        email="admin_archive_test@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Admin Archiver",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    customer = User(
        email="customer_archive_test@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Test Customer",
        role=UserRole.CUSTOMER,
        is_active=True,
        is_verified=True,
    )
    owner = User(
        email="historical_owner@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Historical Kitchen Owner",
        role=UserRole.KITCHEN_OWNER,
        is_active=True,
        is_verified=True,
    )
    db_session.add_all([admin, customer, owner])
    db_session.commit()

    kitchen = KitchenProfile(
        user_id=owner.id,
        kitchen_name="Historical Past Cloud Kitchen",
        address="99 History Road",
        city="Warangal",
        is_approved=True,
        is_open=True,
        approval_status="APPROVED",
    )
    db_session.add(kitchen)
    db_session.commit()

    order = Order(
        customer_id=customer.id,
        kitchen_id=kitchen.id,
        order_number="ORD-HISTORICAL-999",
        subtotal=450.0,
        total_amount=450.0,
        status=OrderStatus.DELIVERED,
    )
    db_session.add(order)
    db_session.commit()

    payment = Payment(
        order_id=order.id,
        amount=450.0,
        currency="INR",
        payment_provider="SIMULATED",
        status=PaymentStatus.SUCCESS,
    )
    db_session.add(payment)
    db_session.commit()

    _login_as(client, admin.email)

    resp = client.delete(f"/api/v1/admin/kitchen-owners/{kitchen.id}")
    assert resp.status_code == 200
    assert resp.json()["action"] == "archived"

    # Verify soft-deletion / archival in database
    db_session.refresh(kitchen)
    db_session.refresh(owner)
    assert kitchen.approval_status == "ARCHIVED"
    assert kitchen.is_approved is False
    assert kitchen.is_open is False
    assert owner.is_active is False

    # Financial & order ledger records strictly preserved
    assert db_session.query(Order).filter(Order.id == order.id).first() is not None
    assert db_session.query(Payment).filter(Payment.id == payment.id).first() is not None


def test_orphaned_kitchen_owner_cleanup(client: TestClient, db_session: Session):
    """An orphaned kitchen owner user without a kitchen profile can be cleaned up safely."""
    admin = User(
        email="admin_orphan_test@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Admin Orphan Handler",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    orphan_user = User(
        email="orphaned_applicant@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Orphaned Applicant",
        role=UserRole.KITCHEN_OWNER,
        is_active=False,
        is_verified=False,
    )
    db_session.add_all([admin, orphan_user])
    db_session.commit()

    u_id = orphan_user.id

    _login_as(client, admin.email)

    # Delete orphaned owner by User ID
    resp = client.delete(f"/api/v1/admin/kitchen-owners/{u_id}")
    assert resp.status_code == 200
    assert resp.json()["action"] in ("deleted", "removed")

    # User removed from DB
    assert db_session.query(User).filter(User.id == u_id).first() is None

    # Audit log entry exists
    audit = db_session.query(AuditLog).filter(
        AuditLog.action == "ORPHANED_KITCHEN_OWNER_DELETED",
        AuditLog.entity_id == u_id,
    ).first()
    assert audit is not None
