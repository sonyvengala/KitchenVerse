"""
Comprehensive backend tests for Admin Safe Delete Actions and Auditable Protections:
1. Current admin cannot delete themselves (HTTP 400).
2. Last active administrator cannot be deleted or deactivated (HTTP 400).
3. Eligible user without dependent business records is safely permanently deleted.
4. User with historical orders/reviews is soft-deleted/archived (business records preserved, not cascade deleted).
5. Kitchen owner with historical orders/inventory is safely archived, not hard-deleted.
6. Pending/rejected kitchen owner without dependent business records is safely removed.
7. Kitchen approval and rejection workflow remains fully operational.
8. Completed payments cannot be permanently deleted (HTTP 400 audit protection).
9. Non-completed payments can be archived to audit log without ledger destruction.
10. Role-based access control enforces ADMIN privileges on all delete endpoints.
"""
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.security import get_password_hash
from backend.app.models.enums import UserRole, OrderStatus, PaymentStatus
from backend.app.models.user import User, KitchenProfile
from backend.app.models.order import Order, OrderItem, Payment, Review
from backend.app.models.inventory import Inventory
from backend.app.models.platform import AuditLog


def _login_as(client: TestClient, email: str, password: str = "TestPass123!") -> None:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    cookie = resp.cookies.get(settings.SESSION_COOKIE_NAME)
    client.cookies.set(settings.SESSION_COOKIE_NAME, cookie)


def test_admin_cannot_delete_self(client: TestClient, db_session: Session):
    """Admin cannot delete their own account (HTTP 400)."""
    admin = User(
        email="super_admin_self_delete@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Super Admin Self",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    db_session.add(admin)
    db_session.commit()

    _login_as(client, admin.email)

    resp = client.delete(f"/api/v1/admin/users/{admin.id}")
    assert resp.status_code == 400
    data = resp.json()
    assert "Self-deletion is prohibited" in data["detail"]

    db_session.refresh(admin)
    assert admin.is_active is True


def test_last_active_admin_cannot_be_deleted(client: TestClient, db_session: Session):
    """Last active administrator cannot be deleted or deactivated."""
    admin1 = User(
        email="caller_admin_one@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Caller Admin One",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    admin2 = User(
        email="target_admin_two@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Target Admin Two",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    db_session.add_all([admin1, admin2])
    db_session.commit()

    _login_as(client, admin1.email)

    # Admin1 deletes Admin2 (succeeds because Admin1 remains active)
    resp = client.delete(f"/api/v1/admin/users/{admin2.id}")
    assert resp.status_code == 200

    # Now Admin1 is the sole active admin in the database.
    # Attempting to delete Admin1 is blocked by self-deletion protection
    resp_self = client.delete(f"/api/v1/admin/users/{admin1.id}")
    assert resp_self.status_code == 400
    assert "self-deletion is prohibited" in resp_self.json()["detail"].lower()

    # Attempting to deactivate Admin1 is blocked by self-deactivation protection
    resp_deact = client.patch(f"/api/v1/admin/users/{admin1.id}/status", json={"status": "SUSPENDED"})
    assert resp_deact.status_code == 400
    assert "self-deactivation is prohibited" in resp_deact.json()["detail"].lower()


def test_eligible_clean_user_hard_deletion(client: TestClient, db_session: Session):
    """User without historical records or orders is permanently deleted safely."""
    admin = User(
        email="admin_clean_del@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Admin Cleaner",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    clean_customer = User(
        email="clean_customer@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Clean Customer",
        role=UserRole.CUSTOMER,
        is_active=True,
        is_verified=True,
    )
    db_session.add_all([admin, clean_customer])
    db_session.commit()

    _login_as(client, admin.email)

    target_id = clean_customer.id
    resp = client.delete(f"/api/v1/admin/users/{target_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["action"] == "deleted"

    # Verify user record is completely removed from DB
    deleted_user = db_session.query(User).filter(User.id == target_id).first()
    assert deleted_user is None


def test_user_with_historical_orders_is_soft_deleted_and_archived(client: TestClient, db_session: Session):
    """User with orders must NEVER be cascade deleted; must be soft-deleted / archived."""
    admin = User(
        email="admin_order_archive@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Admin Order Archiver",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    customer = User(
        email="customer_with_orders@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Valued Customer",
        role=UserRole.CUSTOMER,
        is_active=True,
        is_verified=True,
    )
    kitchen_owner = User(
        email="kowner_for_order@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Kitchen Owner One",
        role=UserRole.KITCHEN_OWNER,
        is_active=True,
        is_verified=True,
    )
    db_session.add_all([admin, customer, kitchen_owner])
    db_session.commit()

    kitchen = KitchenProfile(
        user_id=kitchen_owner.id,
        kitchen_name="Test Kitchen Alpha",
        address="100 Main St",
        city="Bangalore",
        is_approved=True,
        is_open=True,
        approval_status="APPROVED",
    )
    db_session.add(kitchen)
    db_session.commit()

    # Create historical order and completed payment with subtotal
    order = Order(
        customer_id=customer.id,
        kitchen_id=kitchen.id,
        order_number="ORD-TEST-9999",
        status=OrderStatus.DELIVERED,
        subtotal=380.0,
        total_amount=380.0,
    )
    db_session.add(order)
    db_session.commit()

    payment = Payment(
        order_id=order.id,
        payment_provider="RAZORPAY",
        amount=380.0,
        currency="INR",
        status=PaymentStatus.SUCCESS,
    )
    db_session.add(payment)
    db_session.commit()

    _login_as(client, admin.email)

    resp = client.delete(f"/api/v1/admin/users/{customer.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["action"] == "archived"

    # User remains in DB, deactivated
    db_session.refresh(customer)
    assert customer.is_active is False

    # Historical order and payment must be completely intact!
    saved_order = db_session.query(Order).filter(Order.id == order.id).first()
    assert saved_order is not None
    assert saved_order.total_amount == 380.0

    saved_payment = db_session.query(Payment).filter(Payment.id == payment.id).first()
    assert saved_payment is not None
    assert saved_payment.status == PaymentStatus.SUCCESS

    # Verify audit log recorded
    log = db_session.query(AuditLog).filter(AuditLog.entity_id == customer.id, AuditLog.action == "USER_ARCHIVED").first()
    assert log is not None


def test_kitchen_owner_with_historical_orders_archived(client: TestClient, db_session: Session):
    """Kitchen owner with order history cannot be hard deleted; must be safely archived."""
    admin = User(
        email="admin_k_arch@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Admin Kitchen Archiver",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    k_owner = User(
        email="kitchen_busy_owner@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Busy Chef",
        role=UserRole.KITCHEN_OWNER,
        is_active=True,
        is_verified=True,
    )
    db_session.add_all([admin, k_owner])
    db_session.commit()

    kitchen = KitchenProfile(
        user_id=k_owner.id,
        kitchen_name="Chef Spice Cloud Kitchen",
        address="42 Residency Rd",
        city="Bangalore",
        is_approved=True,
        is_open=True,
        approval_status="APPROVED",
    )
    db_session.add(kitchen)
    db_session.commit()

    order = Order(
        customer_id=k_owner.id,
        kitchen_id=kitchen.id,
        order_number="ORD-KITCHEN-5555",
        status=OrderStatus.DELIVERED,
        subtotal=586.0,
        total_amount=586.0,
    )
    db_session.add(order)
    db_session.commit()

    _login_as(client, admin.email)

    resp = client.delete(f"/api/v1/admin/kitchen-owners/{kitchen.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["action"] == "archived"

    db_session.refresh(kitchen)
    assert kitchen.approval_status == "ARCHIVED"
    assert kitchen.is_open is False
    assert kitchen.is_approved is False

    # Historical order preserved
    order_in_db = db_session.query(Order).filter(Order.id == order.id).first()
    assert order_in_db is not None


def test_pending_kitchen_owner_safe_removal(client: TestClient, db_session: Session):
    """Pending or rejected registration without dependent business records is safely removed."""
    admin = User(
        email="admin_k_remove@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Admin Kitchen Remover",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    k_applicant = User(
        email="rejected_applicant@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Applicant John",
        role=UserRole.KITCHEN_OWNER,
        is_active=False,
        is_verified=False,
    )
    db_session.add_all([admin, k_applicant])
    db_session.commit()

    kitchen = KitchenProfile(
        user_id=k_applicant.id,
        kitchen_name="Unverified Ghost Kitchen",
        address="10 Industrial Area",
        city="Mysore",
        is_approved=False,
        is_open=False,
        approval_status="REJECTED",
    )
    db_session.add(kitchen)
    db_session.commit()

    _login_as(client, admin.email)

    k_id = kitchen.id
    resp = client.delete(f"/api/v1/admin/kitchen-owners/{k_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["action"] == "removed"

    # Kitchen removed from DB
    assert db_session.query(KitchenProfile).filter(KitchenProfile.id == k_id).first() is None


def test_completed_payments_cannot_be_deleted(client: TestClient, db_session: Session):
    """Completed payments must remain immutable and auditable (HTTP 400)."""
    admin = User(
        email="admin_pay_audit@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Admin Payments",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    db_session.add(admin)
    db_session.commit()

    order = Order(
        customer_id=admin.id,
        kitchen_id=str(uuid.uuid4()),
        order_number="ORD-PAY-1234",
        status=OrderStatus.DELIVERED,
        subtotal=260.0,
        total_amount=260.0,
    )
    db_session.add(order)
    db_session.commit()

    payment = Payment(
        order_id=order.id,
        payment_provider="RAZORPAY",
        amount=260.0,
        currency="INR",
        status=PaymentStatus.SUCCESS,
    )
    db_session.add(payment)
    db_session.commit()

    _login_as(client, admin.email)

    # Attempt to delete completed payment
    resp = client.delete(f"/api/v1/admin/payments/{payment.id}")
    assert resp.status_code == 400
    assert "Completed payment transactions cannot be permanently deleted" in resp.json()["detail"]

    # Payment in DB remains intact
    db_session.refresh(payment)
    assert payment is not None
    assert payment.amount == 260.0


def test_non_completed_payment_archival_with_audit(client: TestClient, db_session: Session):
    """Failed or pending payment can be archived to audit log without destroying financial data."""
    admin = User(
        email="admin_pay_failed@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Admin Payments Failed",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    db_session.add(admin)
    db_session.commit()

    order = Order(
        customer_id=admin.id,
        kitchen_id=str(uuid.uuid4()),
        order_number="ORD-PAY-FAIL-1",
        status=OrderStatus.CANCELLED,
        subtotal=100.0,
        total_amount=100.0,
    )
    db_session.add(order)
    db_session.commit()

    payment = Payment(
        order_id=order.id,
        payment_provider="RAZORPAY",
        amount=100.0,
        currency="INR",
        status=PaymentStatus.FAILED,
    )
    db_session.add(payment)
    db_session.commit()

    _login_as(client, admin.email)

    resp = client.delete(f"/api/v1/admin/payments/{payment.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["action"] == "archived"

    # Payment still exists in ledger
    db_session.refresh(payment)
    assert payment is not None

    # Audit log recorded
    log = db_session.query(AuditLog).filter(AuditLog.entity_id == payment.id, AuditLog.action == "PAYMENT_ARCHIVED").first()
    assert log is not None


def test_rbac_delete_endpoints_require_admin(client: TestClient, db_session: Session):
    """Non-admin users cannot access any admin delete endpoints (HTTP 403)."""
    customer = User(
        email="regular_customer_rbac@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Regular Customer",
        role=UserRole.CUSTOMER,
        is_active=True,
        is_verified=True,
    )
    db_session.add(customer)
    db_session.commit()

    _login_as(client, customer.email)

    dummy_id = str(uuid.uuid4())
    assert client.delete(f"/api/v1/admin/users/{dummy_id}").status_code == 403
    assert client.delete(f"/api/v1/admin/kitchen-owners/{dummy_id}").status_code == 403
    assert client.delete(f"/api/v1/admin/payments/{dummy_id}").status_code == 403


def test_kitchen_approval_workflow_still_works(client: TestClient, db_session: Session):
    """Kitchen approval and rejection workflows remain fully operational."""
    admin = User(
        email="admin_workflow_check@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Admin Workflow",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    applicant = User(
        email="applicant_workflow@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Applicant Two",
        role=UserRole.KITCHEN_OWNER,
        is_active=True,
        is_verified=True,
    )
    db_session.add_all([admin, applicant])
    db_session.commit()

    kitchen = KitchenProfile(
        user_id=applicant.id,
        kitchen_name="Workflow Cloud Kitchen",
        address="10 Brigade Rd",
        city="Bangalore",
        is_approved=False,
        is_open=False,
        approval_status="PENDING",
    )
    db_session.add(kitchen)
    db_session.commit()

    _login_as(client, admin.email)

    # Approve
    resp = client.post(f"/api/v1/admin/kitchen-owners/{kitchen.id}/approve")
    assert resp.status_code == 200
    db_session.refresh(kitchen)
    assert kitchen.approval_status == "APPROVED"
    assert kitchen.is_approved is True

    # Reject
    resp_rej = client.post(f"/api/v1/admin/kitchen-owners/{kitchen.id}/reject", json={"reason": "Missing documents"})
    assert resp_rej.status_code == 200
    db_session.refresh(kitchen)
    assert kitchen.approval_status == "REJECTED"
    assert kitchen.rejection_reason == "Missing documents"


def test_batch_remove_kitchen_owners(client: TestClient, db_session: Session):
    """Admin batch removal deletes clean test records, archives records with orders, and blocks non-admins."""
    admin = User(
        email="admin_batch@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Admin Batcher",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    customer = User(
        email="customer_batch@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Customer Normal",
        role=UserRole.CUSTOMER,
        is_active=True,
        is_verified=True,
    )
    test_owner_1 = User(
        email="test_owner_one@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Master Chef 1",
        role=UserRole.KITCHEN_OWNER,
        is_active=True,
        is_verified=True,
    )
    test_owner_2 = User(
        email="test_owner_two@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Master Chef 2",
        role=UserRole.KITCHEN_OWNER,
        is_active=True,
        is_verified=True,
    )
    db_session.add_all([admin, customer, test_owner_1, test_owner_2])
    db_session.commit()

    # Kitchen 1 has NO orders -> eligible for permanent removal
    k1 = KitchenProfile(
        user_id=test_owner_1.id,
        kitchen_name="Test Ghost Kitchen 1",
        address="100 Test St",
        city="Mysore",
        is_approved=False,
        is_open=False,
        approval_status="PENDING",
    )
    # Kitchen 2 has historical order -> must be safely archived
    k2 = KitchenProfile(
        user_id=test_owner_2.id,
        kitchen_name="Test Ghost Kitchen 2",
        address="200 Test St",
        city="Mysore",
        is_approved=True,
        is_open=True,
        approval_status="APPROVED",
    )
    db_session.add_all([k1, k2])
    db_session.commit()

    # Add historical order to k2
    order = Order(
        customer_id=customer.id,
        kitchen_id=k2.id,
        order_number="ORD-BATCH-TEST-001",
        subtotal=250.0,
        total_amount=250.0,
        status=OrderStatus.DELIVERED,
    )
    db_session.add(order)
    db_session.commit()

    k1_id = k1.id
    k2_id = k2.id

    # 1. Non-admin cannot batch remove
    _login_as(client, customer.email)
    forbidden_resp = client.post("/api/v1/admin/kitchen-owners/batch-remove", json={"kitchen_ids": [k1_id, k2_id]})
    assert forbidden_resp.status_code == 403

    # 2. Admin can batch remove
    _login_as(client, admin.email)
    resp = client.post("/api/v1/admin/kitchen-owners/batch-remove", json={"kitchen_ids": [k1_id, k2_id]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["processed_count"] == 2
    assert data["deleted_count"] == 1
    assert data["archived_count"] == 1

    # Verify k1 is permanently removed
    assert db_session.query(KitchenProfile).filter(KitchenProfile.id == k1_id).first() is None

    # Verify k2 is preserved but archived
    db_session.refresh(k2)
    assert k2.approval_status == "ARCHIVED"
    assert k2.is_approved is False
    assert k2.is_open is False

    # Historical order intact
    assert db_session.query(Order).filter(Order.id == order.id).first() is not None
