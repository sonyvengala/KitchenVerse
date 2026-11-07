"""
Regression tests for Kitchen Owner Waste, Admin Waste, and Admin Reviews.
Verifies RBAC, empty data safety, real relationship serialization, and data isolation.
"""
import pytest
from datetime import datetime, timezone
import uuid
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from backend.app.models.user import User, KitchenProfile
from backend.app.models.enums import UserRole, OrderStatus
from backend.app.models.menu import MenuItem, Ingredient
from backend.app.models.inventory import WasteRecord
from backend.app.models.order import Order, Review
from backend.app.core.session import create_user_session
from backend.app.core.security import get_password_hash


def _create_user_with_session(db: Session, email: str, role: UserRole) -> tuple[User, str]:
    user = User(
        id=str(uuid.uuid4()),
        email=email,
        hashed_password=get_password_hash("TestPass123!"),
        full_name=f"Test {role.value}",
        role=role,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    session = create_user_session(db, user.id)
    return user, session.session_id


def _create_kitchen(db: Session, owner: User, name: str = "Test Kitchen") -> KitchenProfile:
    kitchen = KitchenProfile(
        id=str(uuid.uuid4()),
        user_id=owner.id,
        kitchen_name=name,
        address="123 Test St",
        city="Bengaluru",
        is_approved=True,
        is_open=True,
    )
    db.add(kitchen)
    db.commit()
    db.refresh(kitchen)
    return kitchen


# ==============================================================================
# 1. KITCHEN OWNER WASTE MANAGEMENT TESTS
# ==============================================================================

def test_kitchen_owner_can_retrieve_own_waste(client: TestClient, db_session: Session):
    owner, session_id = _create_user_with_session(db_session, "ko_waste_1@test.com", UserRole.KITCHEN_OWNER)
    kitchen = _create_kitchen(db_session, owner, "Kitchen One")

    ing = Ingredient(
        id=str(uuid.uuid4()),
        kitchen_id=kitchen.id,
        name="Tomato",
        unit="kg",
        current_stock=10.0,
        minimum_stock_threshold=2.0,
    )
    db_session.add(ing)
    db_session.commit()

    waste = WasteRecord(
        id=str(uuid.uuid4()),
        kitchen_id=kitchen.id,
        ingredient_id=ing.id,
        quantity=1.5,
        unit="kg",
        reason="Spoiled",
        recorded_by=owner.email,
        estimated_cost=45.0,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(waste)
    db_session.commit()

    headers = {"Authorization": f"Bearer {session_id}"}
    res = client.get("/api/v1/kitchen/waste", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["ingredient_name"] == "Tomato"
    assert data[0]["quantity"] == 1.5
    assert data[0]["estimated_cost"] == 45.0


def test_kitchen_owner_cannot_retrieve_another_kitchen_waste(client: TestClient, db_session: Session):
    owner1, session_id1 = _create_user_with_session(db_session, "ko_waste_sec1@test.com", UserRole.KITCHEN_OWNER)
    kitchen1 = _create_kitchen(db_session, owner1, "Kitchen One")

    owner2, _ = _create_user_with_session(db_session, "ko_waste_sec2@test.com", UserRole.KITCHEN_OWNER)
    kitchen2 = _create_kitchen(db_session, owner2, "Kitchen Two")

    # Add waste to kitchen 2
    waste2 = WasteRecord(
        id=str(uuid.uuid4()),
        kitchen_id=kitchen2.id,
        quantity=5.0,
        unit="kg",
        reason="Other kitchen waste",
        recorded_by="other@test.com",
        estimated_cost=100.0,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(waste2)
    db_session.commit()

    # Owner 1 queries own waste
    headers = {"Authorization": f"Bearer {session_id1}"}
    res = client.get("/api/v1/kitchen/waste", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) == 0


def test_kitchen_owner_zero_waste_and_analytics_safety(client: TestClient, db_session: Session):
    owner, session_id = _create_user_with_session(db_session, "ko_empty_waste@test.com", UserRole.KITCHEN_OWNER)
    _create_kitchen(db_session, owner, "Empty Kitchen")

    headers = {"Authorization": f"Bearer {session_id}"}
    res_records = client.get("/api/v1/kitchen/waste", headers=headers)
    assert res_records.status_code == 200
    assert res_records.json() == []

    res_an = client.get("/api/v1/kitchen/waste/analytics", headers=headers)
    assert res_an.status_code == 200
    an_data = res_an.json()
    assert an_data["total_cost"] == 0.0
    assert an_data["wasted_orders_count"] == 0
    assert an_data["total_wasted_portions"] == 0.0
    assert an_data["wastage_rate"] == 0.0
    assert an_data["by_reason"] == []
    assert an_data["by_menu_item"] == []
    assert an_data["by_ingredient"] == []
    assert len(an_data["monthly_trend"]) == 6


def test_kitchen_waste_unauthorized_access(client: TestClient, db_session: Session):
    cust, cust_session_id = _create_user_with_session(db_session, "cust_waste_unauth@test.com", UserRole.CUSTOMER)
    headers = {"Authorization": f"Bearer {cust_session_id}"}
    res = client.get("/api/v1/kitchen/waste", headers=headers)
    assert res.status_code == 403


# ==============================================================================
# 2. ADMIN WASTE MANAGEMENT TESTS
# ==============================================================================

def test_admin_can_retrieve_all_waste(client: TestClient, db_session: Session):
    admin, admin_session_id = _create_user_with_session(db_session, "admin_waste_1@test.com", UserRole.ADMIN)
    owner, _ = _create_user_with_session(db_session, "ko_admin_waste_src@test.com", UserRole.KITCHEN_OWNER)
    kitchen = _create_kitchen(db_session, owner, "Platform Kitchen")

    waste = WasteRecord(
        id=str(uuid.uuid4()),
        kitchen_id=kitchen.id,
        quantity=3.0,
        unit="kg",
        reason="Burned",
        recorded_by="Staff",
        estimated_cost=90.0,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(waste)
    db_session.commit()

    headers = {"Authorization": f"Bearer {admin_session_id}"}
    res = client.get("/admin/waste", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    record = data["waste_records"][0]
    assert record["cost"] == 90.0
    assert record["recorded_at"] is not None
    assert record["kitchen"]["kitchen_name"] == "Platform Kitchen"
    assert "summary" in data
    assert data["summary"]["total_cost"] == 90.0


def test_admin_waste_empty_data_safety(client: TestClient, db_session: Session):
    admin, admin_session_id = _create_user_with_session(db_session, "admin_waste_empty@test.com", UserRole.ADMIN)
    headers = {"Authorization": f"Bearer {admin_session_id}"}
    res = client.get("/admin/waste", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["waste_records"] == []
    assert data["total"] == 0
    assert data["summary"]["total_cost"] == 0.0


def test_admin_waste_non_admin_rejected(client: TestClient, db_session: Session):
    cust, cust_session_id = _create_user_with_session(db_session, "cust_admin_waste@test.com", UserRole.CUSTOMER)
    owner, ko_session_id = _create_user_with_session(db_session, "ko_admin_waste_deny@test.com", UserRole.KITCHEN_OWNER)

    res_cust = client.get("/admin/waste", headers={"Authorization": f"Bearer {cust_session_id}"})
    assert res_cust.status_code == 403

    res_ko = client.get("/admin/waste", headers={"Authorization": f"Bearer {ko_session_id}"})
    assert res_ko.status_code == 403


# ==============================================================================
# 3. ADMIN REVIEWS TESTS
# ==============================================================================

def test_admin_can_retrieve_reviews_and_serialization(client: TestClient, db_session: Session):
    admin, admin_session_id = _create_user_with_session(db_session, "admin_rev_1@test.com", UserRole.ADMIN)
    owner, _ = _create_user_with_session(db_session, "ko_rev_1@test.com", UserRole.KITCHEN_OWNER)
    kitchen = _create_kitchen(db_session, owner, "Biryani House")
    cust, _ = _create_user_with_session(db_session, "cust_reviewer_1@test.com", UserRole.CUSTOMER)

    order = Order(
        id=str(uuid.uuid4()),
        order_number="ORD-TEST-REV-01",
        customer_id=cust.id,
        kitchen_id=kitchen.id,
        status=OrderStatus.DELIVERED,
        total_amount=250.0,
        subtotal=200.0,
        tax=20.0,
        delivery_fee=30.0,
    )
    db_session.add(order)
    db_session.commit()

    review = Review(
        id=str(uuid.uuid4()),
        order_id=order.id,
        customer_id=cust.id,
        kitchen_id=kitchen.id,
        rating=5,
        comment="Absolutely delicious!",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(review)
    db_session.commit()

    headers = {"Authorization": f"Bearer {admin_session_id}"}
    res = client.get("/admin/reviews", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    rev_data = data["reviews"][0]
    assert rev_data["rating"] == 5
    assert rev_data["comment"] == "Absolutely delicious!"
    assert rev_data["customer"]["name"] == cust.full_name
    assert rev_data["order_number"] == "ORD-TEST-REV-01"
    assert rev_data["kitchen"]["kitchen_name"] == "Biryani House"


def test_admin_reviews_empty_data_safety(client: TestClient, db_session: Session):
    admin, admin_session_id = _create_user_with_session(db_session, "admin_rev_empty@test.com", UserRole.ADMIN)
    headers = {"Authorization": f"Bearer {admin_session_id}"}
    res = client.get("/admin/reviews", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["reviews"] == []
    assert data["total"] == 0


def test_admin_reviews_non_admin_rejected(client: TestClient, db_session: Session):
    cust, cust_session_id = _create_user_with_session(db_session, "cust_rev_deny@test.com", UserRole.CUSTOMER)
    owner, ko_session_id = _create_user_with_session(db_session, "ko_rev_deny@test.com", UserRole.KITCHEN_OWNER)

    res_cust = client.get("/admin/reviews", headers={"Authorization": f"Bearer {cust_session_id}"})
    assert res_cust.status_code == 403

    res_ko = client.get("/admin/reviews", headers={"Authorization": f"Bearer {ko_session_id}"})
    assert res_ko.status_code == 403
