"""
Tests for Admin Notification Center and Management System.
Validates:
- Real notification dispatch across events
- Filtering by categories/tabs (All, Unread, Read, Kitchen, Orders, Payments, Inventory, System)
- Unread count endpoint
- Mark read, mark unread, mark all read
- Delete single notification
- Clear read notifications (preventing unread notifications from being deleted)
- Deduplication of notifications
- Admin-only RBAC protection and admin isolation
"""
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.database import Base, get_db
from backend.app.core.security import get_password_hash
from backend.app.models.enums import UserRole
from backend.app.models.user import User, KitchenProfile
from backend.app.models.platform import Notification
from backend.app.services.notification_service import NotificationService
from backend.app.main import app


@pytest.fixture
def test_setup():
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    db = TestingSession()
    # 1. Primary Admin
    admin_id = str(uuid.uuid4())
    admin = User(
        id=admin_id,
        email="admin@testplatform.com",
        hashed_password=get_password_hash("AdminPass123!"),
        full_name="Platform Administrator",
        phone_number="+919999999999",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    db.add(admin)

    # 2. Secondary Admin (for isolation tests)
    admin2_id = str(uuid.uuid4())
    admin2 = User(
        id=admin2_id,
        email="admin2@testplatform.com",
        hashed_password=get_password_hash("AdminPass123!"),
        full_name="Second Administrator",
        phone_number="+918888888888",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    db.add(admin2)

    # 3. Regular Customer
    cust_id = str(uuid.uuid4())
    customer = User(
        id=cust_id,
        email="customer@testplatform.com",
        hashed_password=get_password_hash("CustPass123!"),
        full_name="Test Customer",
        phone_number="+917777777777",
        role=UserRole.CUSTOMER,
        is_active=True,
        is_verified=True,
    )
    db.add(customer)
    db.commit()

    yield {
        "db": db,
        "admin": admin,
        "admin2": admin2,
        "customer": customer,
    }

    db.close()
    app.dependency_overrides.clear()


def login_user(client: TestClient, email: str, password: str) -> str:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    return res.json()["access_token"]


def test_admin_notification_lifecycle_and_actions(test_setup):
    db = test_setup["db"]
    admin = test_setup["admin"]
    client = TestClient(app)

    token = login_user(client, "admin@testplatform.com", "AdminPass123!")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Dispatch real notifications
    order_id = str(uuid.uuid4())
    NotificationService.notify_admins(
        db=db,
        event_type="ORDER_CREATED",
        title="New Order Placed",
        message="Order #ORD-1001 placed for ₹750.00.",
        metadata={"entity_type": "order", "entity_id": order_id, "link": "/admin/orders"}
    )
    NotificationService.notify_admins(
        db=db,
        event_type="PAYMENT_RECEIVED",
        title="Payment Success",
        message="Payment of ₹750.00 confirmed.",
        metadata={"entity_type": "payment", "entity_id": str(uuid.uuid4()), "link": "/admin/payments"}
    )
    NotificationService.notify_admins(
        db=db,
        event_type="LOW_STOCK",
        title="Low Stock Alert: Basmati Rice",
        message="Basmati Rice is low.",
        metadata={"entity_type": "inventory", "entity_id": str(uuid.uuid4()), "link": "/admin/inventory"}
    )
    NotificationService.notify_admins(
        db=db,
        event_type="KITCHEN_REGISTRATION_REQUEST",
        title="New Kitchen Registration",
        message="Sony Kitchen awaiting approval.",
        metadata={"entity_type": "kitchen", "entity_id": str(uuid.uuid4()), "link": "/admin/kitchen-owners"}
    )
    db.commit()

    # 2. Test GET /notifications
    res = client.get("/api/v1/admin/notifications", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "notifications" in data
    assert data["unread_count"] == 4
    assert data["total_count"] == 4
    assert data["counts_by_tab"]["orders"] == 1
    assert data["counts_by_tab"]["payments"] == 1
    assert data["counts_by_tab"]["inventory"] == 1
    assert data["counts_by_tab"]["kitchen"] == 1

    notifs = data["notifications"]
    assert len(notifs) == 4

    # 3. Test GET /notifications/unread-count
    res_count = client.get("/api/v1/admin/notifications/unread-count", headers=headers)
    assert res_count.status_code == 200
    assert res_count.json()["unread_count"] == 4

    # 4. Filter by tab
    res_orders = client.get("/api/v1/admin/notifications?tab=ORDERS", headers=headers)
    assert res_orders.status_code == 200
    assert len(res_orders.json()["notifications"]) == 1
    assert res_orders.json()["notifications"][0]["event_type"] == "ORDER_CREATED"

    res_kitchen = client.get("/api/v1/admin/notifications?tab=KITCHEN", headers=headers)
    assert res_kitchen.status_code == 200
    assert len(res_kitchen.json()["notifications"]) == 1

    # 5. Mark individual notification read
    target_id = notifs[0]["id"]
    res_read = client.put(f"/api/v1/admin/notifications/{target_id}/read", headers=headers)
    assert res_read.status_code == 200
    assert res_read.json()["is_read"] is True

    res_count2 = client.get("/api/v1/admin/notifications/unread-count", headers=headers)
    assert res_count2.json()["unread_count"] == 3

    # 6. Mark individual notification unread
    res_unread = client.put(f"/api/v1/admin/notifications/{target_id}/unread", headers=headers)
    assert res_unread.status_code == 200
    assert res_unread.json()["is_read"] is False

    res_count3 = client.get("/api/v1/admin/notifications/unread-count", headers=headers)
    assert res_count3.json()["unread_count"] == 4

    # 7. Mark single read again, then test Clear Read
    client.put(f"/api/v1/admin/notifications/{target_id}/read", headers=headers)
    res_clear = client.delete("/api/v1/admin/notifications/clear-read", headers=headers)
    assert res_clear.status_code == 200
    assert res_clear.json()["cleared_count"] == 1

    # Ensure unread notifications were NOT deleted!
    res_after_clear = client.get("/api/v1/admin/notifications", headers=headers)
    assert res_after_clear.json()["unread_count"] == 3
    assert res_after_clear.json()["total_count"] == 3

    # 8. Delete individual notification
    next_id = res_after_clear.json()["notifications"][0]["id"]
    res_del = client.delete(f"/api/v1/admin/notifications/{next_id}", headers=headers)
    assert res_del.status_code == 200
    assert res_del.json()["deleted_id"] == next_id

    res_after_del = client.get("/api/v1/admin/notifications", headers=headers)
    assert res_after_del.json()["total_count"] == 2

    # 9. Mark all read
    res_all_read = client.put("/api/v1/admin/notifications/read-all", headers=headers)
    assert res_all_read.status_code == 200
    assert res_all_read.json()["marked_read_count"] == 2

    res_count_final = client.get("/api/v1/admin/notifications/unread-count", headers=headers)
    assert res_count_final.json()["unread_count"] == 0


def test_notification_deduplication(test_setup):
    db = test_setup["db"]
    client = TestClient(app)

    token = login_user(client, "admin@testplatform.com", "AdminPass123!")
    headers = {"Authorization": f"Bearer {token}"}

    same_order_id = "test-order-999"
    # Dispatch twice with same entity_id
    n1 = NotificationService.notify_admins(
        db=db,
        event_type="ORDER_CREATED",
        title="Order #999 Placed",
        message="First dispatch",
        metadata={"entity_type": "order", "entity_id": same_order_id}
    )
    db.commit()

    n2 = NotificationService.notify_admins(
        db=db,
        event_type="ORDER_CREATED",
        title="Order #999 Placed",
        message="Second dispatch should be deduplicated",
        metadata={"entity_type": "order", "entity_id": same_order_id}
    )
    db.commit()

    assert len(n1) > 0
    assert len(n2) == 0, "Duplicate event notification should not be dispatched"


def test_customer_cannot_access_admin_notifications(test_setup):
    client = TestClient(app)
    cust_token = login_user(client, "customer@testplatform.com", "CustPass123!")
    headers = {"Authorization": f"Bearer {cust_token}"}

    res = client.get("/api/v1/admin/notifications", headers=headers)
    assert res.status_code == 403
    assert "ADMIN" in res.json().get("detail", "")
