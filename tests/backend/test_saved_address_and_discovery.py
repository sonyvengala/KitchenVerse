"""
Automated Backend Tests for Saved Address Management & Location-Aware Kitchen Discovery.
Tests:
- Deleting an address owned by authenticated customer
- Preventing deletion of another customer's address (strict RBAC & customer isolation)
- Setting default address and automatic promotion when default is deleted
- Historical order address preservation (snapshots, text, coords preserved; orders never deleted)
- Location-aware kitchen discovery endpoint with coordinates, real road distance, duration, and can_deliver
- Excluding closed, suspended, and unapproved kitchens from discovery
- Missing kitchen coordinates handling without crashes
- Routing service failure graceful fallback to clearly labeled straight-line estimate
- Checkout delivery eligibility and customer address isolation
"""

import json
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.security import get_password_hash
from backend.app.models.enums import UserRole, OrderStatus, PaymentStatus
from backend.app.models.user import User, KitchenProfile, Address
from backend.app.models.menu import MenuItem
from backend.app.models.order import Order
from backend.app.services.delivery_pricing_service import DeliveryPricingService


@pytest.fixture
def test_setup(db_session: Session):
    # Customer 1
    c1 = User(
        email="customer1.address@test.com",
        hashed_password=get_password_hash("Pass123!"),
        full_name="Alice Customer",
        role=UserRole.CUSTOMER,
        is_active=True,
        is_verified=True,
    )
    # Customer 2
    c2 = User(
        email="customer2.address@test.com",
        hashed_password=get_password_hash("Pass123!"),
        full_name="Bob Customer",
        role=UserRole.CUSTOMER,
        is_active=True,
        is_verified=True,
    )
    # Kitchen Owners (each kitchen profile requires a unique user_id)
    owner1 = User(
        email="owner1.address@test.com",
        hashed_password=get_password_hash("Pass123!"),
        full_name="Chef Owner 1",
        role=UserRole.KITCHEN_OWNER,
        is_active=True,
        is_verified=True,
    )
    owner2 = User(
        email="owner2.address@test.com",
        hashed_password=get_password_hash("Pass123!"),
        full_name="Chef Owner 2",
        role=UserRole.KITCHEN_OWNER,
        is_active=True,
        is_verified=True,
    )
    owner3 = User(
        email="owner3.address@test.com",
        hashed_password=get_password_hash("Pass123!"),
        full_name="Chef Owner 3",
        role=UserRole.KITCHEN_OWNER,
        is_active=True,
        is_verified=True,
    )
    owner4 = User(
        email="owner4.address@test.com",
        hashed_password=get_password_hash("Pass123!"),
        full_name="Chef Owner 4",
        role=UserRole.KITCHEN_OWNER,
        is_active=True,
        is_verified=True,
    )
    db_session.add_all([c1, c2, owner1, owner2, owner3, owner4])
    db_session.flush()

    # Kitchen 1: Active, Approved, in Hanamkonda (17.9950, 79.5550)
    k1 = KitchenProfile(
        user_id=owner1.id,
        kitchen_name="Biryani Hub Hanamkonda",
        address="Nakkalagutta, Hanamkonda",
        city="Warangal",
        latitude=17.9950,
        longitude=79.5550,
        is_open=True,
        is_approved=True,
        approval_status="APPROVED",
        rating=4.8,
        rating_count=50,
    )
    # Kitchen 2: Closed kitchen
    k2 = KitchenProfile(
        user_id=owner2.id,
        kitchen_name="Late Night Diner (Closed)",
        address="Subedari, Hanamkonda",
        city="Warangal",
        latitude=17.9980,
        longitude=79.5520,
        is_open=False,
        is_approved=True,
        approval_status="APPROVED",
        rating=4.2,
        rating_count=10,
    )
    # Kitchen 3: Unapproved / suspended kitchen
    k3 = KitchenProfile(
        user_id=owner3.id,
        kitchen_name="Unapproved Kitchen",
        address="Kazipet",
        city="Warangal",
        latitude=17.9800,
        longitude=79.5200,
        is_open=True,
        is_approved=False,
        approval_status="PENDING_REVIEW",
        rating=3.5,
        rating_count=2,
    )
    # Kitchen 4: Kitchen missing coordinates
    k4 = KitchenProfile(
        user_id=owner4.id,
        kitchen_name="No-GPS Kitchen",
        address="Station Road",
        city="Warangal",
        latitude=None,
        longitude=None,
        is_open=True,
        is_approved=True,
        approval_status="APPROVED",
        rating=4.0,
        rating_count=5,
    )
    db_session.add_all([k1, k2, k3, k4])
    db_session.flush()

    # Menu item for Kitchen 1
    m1 = MenuItem(
        kitchen_id=k1.id,
        name="Special Hyderabadi Dum Biryani",
        category="Biryani",
        cuisine="Indian",
        price=280.0,
        is_available=True,
        is_veg=False,
    )
    db_session.add(m1)
    db_session.flush()

    # Saved Addresses for Customer 1
    addr1 = Address(
        user_id=c1.id,
        address_line1="House 12-4, Nakkalagutta",
        city="Warangal",
        state="Telangana",
        postal_code="506001",
        landmark="Near Petrol Bunk",
        latitude=17.9960,
        longitude=79.5560,
        label="Home",
        is_default=True,
    )
    addr2 = Address(
        user_id=c1.id,
        address_line1="Tech Park, Kakatiya University Road",
        city="Warangal",
        state="Telangana",
        postal_code="506009",
        landmark="Block B",
        latitude=18.0200,
        longitude=79.5400,
        label="Work",
        is_default=False,
    )
    # Saved Address for Customer 2
    addr3 = Address(
        user_id=c2.id,
        address_line1="Hostel 4, KITS Campus",
        city="Warangal",
        state="Telangana",
        postal_code="506015",
        label="Home",
        is_default=True,
    )
    db_session.add_all([addr1, addr2, addr3])
    db_session.commit()

    return {
        "c1": c1,
        "c2": c2,
        "addr1": addr1,
        "addr2": addr2,
        "addr3": addr3,
        "k1": k1,
        "k2": k2,
        "k3": k3,
        "k4": k4,
        "m1": m1,
    }


def login_user(client: TestClient, email: str, password: str = "Pass123!"):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed: {res.text}"
    cookie = res.cookies.get(settings.SESSION_COOKIE_NAME)
    client.cookies.set(settings.SESSION_COOKIE_NAME, cookie)
    return cookie


def test_delete_own_address(client: TestClient, db_session: Session, test_setup):
    """Customer can delete their own saved address."""
    login_user(client, test_setup["c1"].email)
    addr2_id = test_setup["addr2"].id

    res = client.delete(f"/api/v1/customer/addresses/{addr2_id}")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["message"] == "Address deleted successfully"
    assert data["deleted_address_id"] == addr2_id

    # Verify deleted from DB
    deleted = db_session.query(Address).filter(Address.id == addr2_id).first()
    assert deleted is None


def test_prevent_deleting_another_customers_address(client: TestClient, test_setup):
    """Customer cannot delete an address owned by another customer."""
    login_user(client, test_setup["c1"].email)
    c2_addr_id = test_setup["addr3"].id

    res = client.delete(f"/api/v1/customer/addresses/{c2_addr_id}")
    assert res.status_code == 403
    assert "not authorized" in res.json()["detail"].lower()


def test_default_promotion_on_default_address_deletion(client: TestClient, db_session: Session, test_setup):
    """When a customer deletes their default address, another address is automatically promoted to default."""
    login_user(client, test_setup["c1"].email)
    default_addr_id = test_setup["addr1"].id
    remaining_addr_id = test_setup["addr2"].id

    res = client.delete(f"/api/v1/customer/addresses/{default_addr_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["new_default_id"] == remaining_addr_id

    # Verify in DB that addr2 is now default
    db_session.expire_all()
    remaining = db_session.query(Address).filter(Address.id == remaining_addr_id).first()
    assert remaining is not None
    assert remaining.is_default is True


def test_historical_order_preservation_on_address_deletion(client: TestClient, db_session: Session, test_setup):
    """Historical orders referencing an address preserve snapshots and text when address is deleted."""
    login_user(client, test_setup["c1"].email)
    c1 = test_setup["c1"]
    addr1 = test_setup["addr1"]
    k1 = test_setup["k1"]

    # Create historical order referencing addr1
    order = Order(
        order_number="ORD-TEST-HISTORICAL-001",
        customer_id=c1.id,
        kitchen_id=k1.id,
        delivery_address_id=addr1.id,
        delivery_address_text=None,  # Intentionally null to test backfill preservation
        delivery_address_snapshot=None,
        delivery_latitude=None,
        delivery_longitude=None,
        status=OrderStatus.DELIVERED,
        subtotal=280.0,
        delivery_fee=25.0,
        tax=14.0,
        total_amount=319.0,
        payment_status=PaymentStatus.SUCCESS,
    )
    db_session.add(order)
    db_session.commit()
    order_id = order.id

    # Delete addr1
    res = client.delete(f"/api/v1/customer/addresses/{addr1.id}")
    assert res.status_code == 200

    # Verify order was NOT deleted
    db_session.expire_all()
    saved_order = db_session.query(Order).filter(Order.id == order_id).first()
    assert saved_order is not None
    # delivery_address_id is safely detached
    assert saved_order.delivery_address_id is None
    # Text, snapshot, and coords were preserved!
    assert "Nakkalagutta" in saved_order.delivery_address_text
    assert saved_order.delivery_address_snapshot is not None
    snap = json.loads(saved_order.delivery_address_snapshot)
    assert snap["address_line1"] == "House 12-4, Nakkalagutta"
    assert saved_order.delivery_latitude == addr1.latitude
    assert saved_order.delivery_longitude == addr1.longitude


def test_set_default_address(client: TestClient, db_session: Session, test_setup):
    """Customer can change their default delivery address."""
    login_user(client, test_setup["c1"].email)
    addr2_id = test_setup["addr2"].id

    res = client.put(f"/api/v1/customer/addresses/{addr2_id}/default")
    assert res.status_code == 200
    data = res.json()
    assert data["is_default"] is True

    db_session.expire_all()
    addr1 = db_session.query(Address).filter(Address.id == test_setup["addr1"].id).first()
    addr2 = db_session.query(Address).filter(Address.id == addr2_id).first()
    assert addr1.is_default is False
    assert addr2.is_default is True


def test_nearby_kitchen_discovery_with_coordinates(client: TestClient, test_setup):
    """Passing customer coordinates returns nearby eligible kitchens with road distance and duration."""
    # Near Hanamkonda (17.9960, 79.5560)
    res = client.get(
        "/api/v1/customer/kitchens",
        params={"latitude": 17.9960, "longitude": 79.5560, "radius_km": 10.0},
    )
    assert res.status_code == 200, res.text
    kitchens = res.json()
    assert len(kitchens) > 0

    k1_result = next((k for k in kitchens if k["id"] == test_setup["k1"].id), None)
    assert k1_result is not None
    assert k1_result["distance_km"] is not None
    assert k1_result["distance_km"] < 2.0
    assert k1_result["can_deliver"] is True
    assert k1_result["distance_type"] in ("driving", "estimated_straight_line")
    assert k1_result["duration_minutes"] is not None


def test_exclude_closed_and_unapproved_kitchens(client: TestClient, test_setup):
    """Closed and unapproved kitchens are excluded from discovery listings."""
    res = client.get(
        "/api/v1/customer/kitchens",
        params={"latitude": 17.9960, "longitude": 79.5560, "radius_km": 15.0},
    )
    assert res.status_code == 200
    kitchens = res.json()
    ids = [k["id"] for k in kitchens]

    # k1 is open and approved -> included
    assert test_setup["k1"].id in ids
    # k2 is closed -> excluded
    assert test_setup["k2"].id not in ids
    # k3 is unapproved -> excluded
    assert test_setup["k3"].id not in ids


def test_kitchen_missing_coordinates_handled_gracefully(client: TestClient, test_setup):
    """Kitchen lacking coordinates does not crash discovery; handled transparently."""
    # When coordinates are provided, k4 (missing coordinates) cannot deliver and is omitted from nearby delivery
    res = client.get(
        "/api/v1/customer/kitchens",
        params={"latitude": 17.9960, "longitude": 79.5560, "radius_km": 10.0},
    )
    assert res.status_code == 200
    kitchens = res.json()
    k4_result = next((k for k in kitchens if k["id"] == test_setup["k4"].id), None)
    assert k4_result is None

    # When no coordinates are passed (global browsing), k4 appears with distance_km = null
    res_global = client.get("/api/v1/customer/kitchens")
    assert res_global.status_code == 200
    global_kitchens = res_global.json()
    k4_global = next((k for k in global_kitchens if k["id"] == test_setup["k4"].id), None)
    assert k4_global is not None
    assert k4_global["distance_km"] is None


def test_routing_failure_fallback_to_estimate(test_setup):
    """When OSRM driving service times out or fails, gracefully falls back to straight-line estimate."""
    with patch("urllib.request.urlopen", side_effect=Exception("OSRM Connection Timeout")):
        route = DeliveryPricingService.calculate_distance(
            17.9950, 79.5550, 18.0200, 79.5400
        )
        assert route["route_available"] is True
        assert route["is_estimate"] is True
        assert route["distance_type"] == "estimated_straight_line"
        assert route["distance_km"] > 0
        assert route["duration_minutes"] > 0


def test_checkout_preview_address_isolation(client: TestClient, test_setup):
    """Checkout preview rejects a delivery address belonging to another customer."""
    login_user(client, test_setup["c1"].email)
    c2_addr_id = test_setup["addr3"].id
    k1_id = test_setup["k1"].id
    m1_id = test_setup["m1"].id

    res = client.post(
        "/api/v1/customer/checkout/preview",
        json={
            "kitchen_id": k1_id,
            "items": [{"menu_item_id": m1_id, "quantity": 1}],
            "delivery_address_id": c2_addr_id,
        },
    )
    assert res.status_code == 403
    assert "not authorized" in res.json()["detail"].lower()
