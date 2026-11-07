"""
Focused integration tests for Customer Portal & Platform Features:
1. Delivery location save & update
2. Missing coordinates actionable error message
3. Delivery route & authorization
4. Customer cancellation UI/API & PREPARING food wastage
5. Add to cart & kitchen conflict isolation
6. Manual image upload & customer portal visibility
7. Resend email verification with 60s rate limit
8. Email verification token validation & checkout guard
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from backend.app.core.security import get_password_hash
from backend.app.models.enums import UserRole, OrderStatus
from backend.app.models.user import User, KitchenProfile, Address
from backend.app.models.menu import MenuItem
from backend.app.models.order import Order


@pytest.fixture
def feature_test_setup(db_session: Session):
    owner = User(
        email="chef.sony@kitchen.com",
        hashed_password=get_password_hash("ChefPass123!"),
        full_name="Chef Sony",
        role=UserRole.KITCHEN_OWNER,
        is_active=True,
        is_verified=True,
    )
    db_session.add(owner)
    db_session.flush()

    kitchen = KitchenProfile(
        user_id=owner.id,
        kitchen_name="Sony's KitchenVerse Kitchen",
        address="100 Culinary Road",
        city="Warangal",
        latitude=18.0049,
        longitude=79.5432,
        is_open=True,
        is_approved=True,
        rating=4.9,
        rating_count=10,
    )
    db_session.add(kitchen)
    db_session.flush()

    dish = MenuItem(
        kitchen_id=kitchen.id,
        name="Chicken Biryani",
        category="Biryani",
        cuisine="Hyderabadi",
        price=220.0,
        is_available=True,
        is_veg=False,
    )
    db_session.add(dish)

    dish2 = MenuItem(
        kitchen_id=kitchen.id,
        name="Masala Dosa",
        category="Breakfast",
        cuisine="South Indian",
        price=120.0,
        is_available=True,
        is_veg=True,
    )
    db_session.add(dish2)

    # Customer 1 (Verified)
    cust_verified = User(
        email="verified.customer@example.com",
        hashed_password=get_password_hash("CustPass123!"),
        full_name="Verified Customer",
        role=UserRole.CUSTOMER,
        is_active=True,
        is_verified=True,
    )
    db_session.add(cust_verified)

    # Customer 2 (Unverified)
    cust_unverified = User(
        email="unverified.customer@example.com",
        hashed_password=get_password_hash("CustPass123!"),
        full_name="Unverified Customer",
        role=UserRole.CUSTOMER,
        is_active=True,
        is_verified=False,
        verification_token="valid_test_token_123",
    )
    db_session.add(cust_unverified)
    db_session.flush()

    addr = Address(
        user_id=cust_verified.id,
        address_line1="45 Lakeview Enclave",
        city="Warangal",
        state="Telangana",
        postal_code="506001",
        latitude=18.0100,
        longitude=79.5500,
        is_default=True,
    )
    db_session.add(addr)
    db_session.commit()

    return {
        "owner": owner,
        "kitchen": kitchen,
        "dish": dish,
        "dish2": dish2,
        "cust_verified": cust_verified,
        "cust_unverified": cust_unverified,
        "address": addr,
    }


def test_unverified_customer_checkout_rejection(client: TestClient, feature_test_setup):
    """Unverified customer cannot place order."""
    data = feature_test_setup
    client.post("/api/v1/auth/login", json={"email": data["cust_unverified"].email, "password": "CustPass123!"})

    res = client.post("/api/v1/customer/orders", json={
        "kitchen_id": data["kitchen"].id,
        "items": [{"menu_item_id": data["dish"].id, "quantity": 1}],
        "payment_method": "CASH_ON_DELIVERY",
    })
    assert res.status_code == 400
    assert "verify your email" in res.json()["detail"].lower()


def test_verified_customer_checkout_success(client: TestClient, feature_test_setup):
    """Verified customer can place order with coordinates preserved."""
    data = feature_test_setup
    client.post("/api/v1/auth/login", json={"email": data["cust_verified"].email, "password": "CustPass123!"})

    res = client.post("/api/v1/customer/orders", json={
        "kitchen_id": data["kitchen"].id,
        "items": [{"menu_item_id": data["dish"].id, "quantity": 1}],
        "delivery_address_id": data["address"].id,
        "payment_method": "CASH_ON_DELIVERY",
    })
    assert res.status_code == 201
    order = res.json()
    assert order["delivery_latitude"] == 18.0100
    assert order["delivery_longitude"] == 79.5500
    assert "45 Lakeview Enclave" in order["delivery_address_text"]


def test_update_order_delivery_location_api(client: TestClient, feature_test_setup, db_session: Session):
    """Customer can update delivery coordinates for active order."""
    data = feature_test_setup
    client.post("/api/v1/auth/login", json={"email": data["cust_verified"].email, "password": "CustPass123!"})

    # Place order
    res = client.post("/api/v1/customer/orders", json={
        "kitchen_id": data["kitchen"].id,
        "items": [{"menu_item_id": data["dish"].id, "quantity": 1}],
        "payment_method": "CASH_ON_DELIVERY",
    })
    order_id = res.json()["id"]

    # Update delivery location
    update_res = client.put(f"/api/v1/customer/orders/{order_id}/delivery-location", json={
        "latitude": 18.0200,
        "longitude": 79.5600,
        "address_text": "Updated Gate 2, Warangal",
    })
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["delivery_latitude"] == 18.0200
    assert updated["delivery_longitude"] == 79.5600
    assert updated["delivery_address_text"] == "Updated Gate 2, Warangal"


def test_delivery_route_actionable_missing_coords(client: TestClient, feature_test_setup, db_session: Session):
    """Route endpoint clearly explains missing customer delivery coordinates."""
    data = feature_test_setup
    client.post("/api/v1/auth/login", json={"email": data["cust_verified"].email, "password": "CustPass123!"})

    res = client.post("/api/v1/customer/orders", json={
        "kitchen_id": data["kitchen"].id,
        "items": [{"menu_item_id": data["dish"].id, "quantity": 1}],
        "payment_method": "CASH_ON_DELIVERY",
    })
    order_id = res.json()["id"]

    # Kitchen owner views route
    client.post("/api/v1/auth/login", json={"email": data["owner"].email, "password": "ChefPass123!"})
    route_res = client.get(f"/api/v1/kitchen/orders/{order_id}/delivery-route")
    assert route_res.status_code == 200
    route = route_res.json()
    assert route["route_available"] is False
    assert "Customer delivery location is not confirmed." in route["message"]


def test_resend_verification_endpoint_and_rate_limit(client: TestClient, feature_test_setup):
    """Resend verification sends email and enforces 60s rate limit."""
    data = feature_test_setup
    # First request
    res1 = client.post("/api/v1/auth/resend-verification", json={"email": data["cust_unverified"].email})
    assert res1.status_code == 200
    assert res1.json()["status"] == "success"
    assert "verification_token" in res1.json()

    # Immediate second request should be rate limited (429)
    res2 = client.post("/api/v1/auth/resend-verification", json={"email": data["cust_unverified"].email})
    assert res2.status_code == 429
    assert "seconds" in res2.json()["detail"].lower()


def test_verify_email_flow_enables_checkout(client: TestClient, feature_test_setup, db_session: Session):
    """Verifying email unlocks checkout for customer."""
    data = feature_test_setup
    user = db_session.query(User).filter(User.id == data["cust_unverified"].id).first()
    token = user.verification_token

    # Verify email
    v_res = client.post("/api/v1/auth/verify-email", json={"token": token})
    assert v_res.status_code == 200

    # User is now verified
    db_session.refresh(user)
    assert user.is_verified is True

    # Login and place order
    client.post("/api/v1/auth/login", json={"email": data["cust_unverified"].email, "password": "CustPass123!"})
    order_res = client.post("/api/v1/customer/orders", json={
        "kitchen_id": data["kitchen"].id,
        "items": [{"menu_item_id": data["dish"].id, "quantity": 1}],
        "payment_method": "CASH_ON_DELIVERY",
    })
    assert order_res.status_code == 201


def test_manual_image_upload_and_persistence(client: TestClient, feature_test_setup, db_session: Session):
    """Manual image upload sets image and displays on customer portal."""
    data = feature_test_setup
    client.post("/api/v1/auth/login", json={"email": data["owner"].email, "password": "ChefPass123!"})

    dish = db_session.query(MenuItem).filter(MenuItem.id == data["dish"].id).first()

    # Upload manual image
    upload_res = client.post(f"/api/v1/kitchen/menu/{dish.id}/upload-image", json={
        "image_url": "/uploads/manual/my_biryani.jpg"
    })
    assert upload_res.status_code == 200
    res_dish = upload_res.json()
    assert res_dish["image_source"] == "MANUAL"
    assert res_dish["manual_image_url"] == "/uploads/manual/my_biryani.jpg"
    assert res_dish["image_url"] == "/uploads/manual/my_biryani.jpg"

    # Customer queries menu and sees image
    menu_res = client.get("/api/v1/customer/menu")
    assert menu_res.status_code == 200
    cust_dish = next((d for d in menu_res.json() if d["id"] == str(dish.id)), None)
    assert cust_dish is not None
    assert cust_dish["image_url"] == "/uploads/manual/my_biryani.jpg"
    assert cust_dish["image_source"] == "MANUAL"
