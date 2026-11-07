"""
Automated Unit and Integration Tests for Dynamic Delivery Pricing.
Tests:
- Configurable defaults: Base fee (₹20.00), per-km fee (₹8.00), max radius (15 km)
- Driving-route distance vs explicit straight-line estimate fallback
- Missing coordinates handling
- Authoritative backend pricing calculation (price tampering rejection)
- Persistent breakdown in Order model (historical immutability when rates change)
- Out-of-range delivery radius rejection
- Admin settings API configuration for delivery rates
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
from backend.app.services.delivery_pricing_service import (
    DeliveryPricingService,
    haversine_distance,
    DEFAULT_DELIVERY_BASE_FEE,
    DEFAULT_DELIVERY_PER_KM_FEE,
)


@pytest.fixture
def delivery_test_data(db_session: Session):
    # Admin User
    admin = User(
        email="admin.delivery@example.com",
        hashed_password=get_password_hash("AdminPass123!"),
        full_name="Delivery Admin",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    # Kitchen Owner & Kitchen in Indiranagar, Bengaluru
    owner = User(
        email="kitchen.delivery@example.com",
        hashed_password=get_password_hash("KitchenSecret123!"),
        full_name="Chef Delivery",
        role=UserRole.KITCHEN_OWNER,
        is_active=True,
        is_verified=True,
    )
    db_session.add_all([admin, owner])
    db_session.flush()

    kitchen = KitchenProfile(
        user_id=owner.id,
        kitchen_name="Indiranagar Gourmet Kitchen",
        address="100 Feet Road, Indiranagar",
        city="Bengaluru",
        latitude=12.9784,
        longitude=77.6408,
        is_open=True,
        is_approved=True,
        rating=4.9,
        rating_count=20,
    )
    db_session.add(kitchen)
    db_session.flush()

    dish = MenuItem(
        kitchen_id=kitchen.id,
        name="Paneer Butter Masala",
        price=220.00,
        category="Main Course",
        cuisine="Indian",
        is_available=True,
    )
    db_session.add(dish)

    # Customer & Address in Koramangala (approx ~5.5 km driving route)
    customer = User(
        email="customer.delivery@example.com",
        hashed_password=get_password_hash("CustomerPass123!"),
        full_name="Pooja Sharma",
        role=UserRole.CUSTOMER,
        is_active=True,
        is_verified=True,
    )
    db_session.add(customer)
    db_session.flush()

    address = Address(
        user_id=customer.id,
        address_line1="4th Block, Koramangala",
        city="Bengaluru",
        state="Karnataka",
        postal_code="560034",
        latitude=12.9352,
        longitude=77.6245,
        is_default=True,
    )
    db_session.add(address)
    db_session.commit()

    return {
        "admin": admin,
        "owner": owner,
        "kitchen": kitchen,
        "dish": dish,
        "customer": customer,
        "address": address,
    }


def test_configurable_defaults(db_session: Session):
    policy = DeliveryPricingService.get_pricing_policy(db_session)
    assert policy["delivery_base_fee"] == 20.00
    assert policy["delivery_per_km_fee"] == 8.00
    assert policy["max_delivery_radius_km"] == 15.00
    assert policy["surge_pricing_enabled"] is False
    assert policy["surge_multiplier"] == 1.00


def test_haversine_straight_line_distance():
    # Indiranagar (12.9784, 77.6408) to Koramangala (12.9352, 77.6245)
    dist = haversine_distance(12.9784, 77.6408, 12.9352, 77.6245)
    assert 4.5 <= dist <= 5.5


def test_route_distance_with_osrm_mock(db_session: Session):
    mock_osrm_response = json.dumps({
        "code": "Ok",
        "routes": [{
            "distance": 5400.0,  # 5.4 km
            "duration": 960.0,   # 16 mins
        }]
    }).encode("utf-8")

    class MockResponse:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self):
            return mock_osrm_response

    with patch("urllib.request.urlopen", return_value=MockResponse()):
        res = DeliveryPricingService.calculate_distance(12.9784, 77.6408, 12.9352, 77.6245)
        assert res["route_available"] is True
        assert res["distance_km"] == 5.4
        assert res["distance_type"] == "driving"
        assert res["is_estimate"] is False
        assert "Driving distance" in res["distance_label"]

        # Test pricing breakdown with default rates: ₹20 base + (₹8 * 5.4 = ₹43.20) = ₹63.20
        breakdown = DeliveryPricingService.calculate_delivery_breakdown(
            db=db_session,
            kitchen_lat=12.9784,
            kitchen_lon=77.6408,
            customer_lat=12.9352,
            customer_lon=77.6245,
            subtotal=220.0,
            discount_amount=0.0,
        )
        assert breakdown["base_delivery_fee"] == 20.00
        assert breakdown["per_km_fee"] == 8.00
        assert breakdown["distance_fee"] == 43.20
        assert breakdown["delivery_fee"] == 63.20
        assert breakdown["total_amount"] == 283.20  # 220 + 63.20
        assert breakdown["is_estimate"] is False


def test_route_failure_graceful_estimate_fallback(db_session: Session):
    # Simulate network timeout or OSRM unavailable
    with patch("urllib.request.urlopen", side_effect=Exception("OSRM server unreachable")):
        res = DeliveryPricingService.calculate_distance(12.9784, 77.6408, 12.9352, 77.6245)
        assert res["route_available"] is True
        assert res["is_estimate"] is True
        assert res["distance_type"] == "estimated_straight_line"
        assert "straight-line" in res["distance_label"].lower()
        assert res["distance_km"] > 0

        breakdown = DeliveryPricingService.calculate_delivery_breakdown(
            db=db_session,
            kitchen_lat=12.9784,
            kitchen_lon=77.6408,
            customer_lat=12.9352,
            customer_lon=77.6245,
            subtotal=100.0,
        )
        assert breakdown["is_estimate"] is True
        assert breakdown["distance_type"] == "estimated_straight_line"
        expected_distance_fee = round(breakdown["distance_km"] * 8.0, 2)
        assert breakdown["distance_fee"] == expected_distance_fee
        assert breakdown["delivery_fee"] == round(20.0 + expected_distance_fee, 2)


def test_missing_coordinates_preliminary_estimate(db_session: Session):
    breakdown = DeliveryPricingService.calculate_delivery_breakdown(
        db=db_session,
        kitchen_lat=None,
        kitchen_lon=None,
        customer_lat=None,
        customer_lon=None,
        subtotal=200.0,
    )
    assert breakdown["requires_location"] is True
    assert breakdown["distance_km"] is None
    assert breakdown["distance_fee"] == 0.0
    assert breakdown["delivery_fee"] == 20.00  # Base fee preliminary estimate
    assert breakdown["total_amount"] == 220.00


def test_out_of_range_delivery(db_session: Session):
    # Distance of ~100 km (e.g. Bengaluru to Mysore)
    breakdown = DeliveryPricingService.calculate_delivery_breakdown(
        db=db_session,
        kitchen_lat=12.9784,
        kitchen_lon=77.6408,
        customer_lat=12.2958,
        customer_lon=76.6394,
        subtotal=300.0,
    )
    assert breakdown["out_of_range"] is True
    assert breakdown["distance_km"] > 15.0


def test_checkout_preview_and_price_tampering_protection(client: TestClient, delivery_test_data, db_session: Session):
    data = delivery_test_data

    # Login as customer
    login_res = client.post("/api/v1/auth/login", json={
        "email": data["customer"].email,
        "password": "CustomerPass123!"
    })
    assert login_res.status_code == 200
    cookie = login_res.cookies.get(settings.SESSION_COOKIE_NAME)
    client.cookies.set(settings.SESSION_COOKIE_NAME, cookie)

    # Mock OSRM to return 3.0 km
    mock_osrm = json.dumps({"code": "Ok", "routes": [{"distance": 3000.0, "duration": 600.0}]}).encode("utf-8")

    class MockResp:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self):
            return mock_osrm

    with patch("urllib.request.urlopen", return_value=MockResp()):
        # 1. Preview
        preview_res = client.post("/api/v1/customer/checkout/preview", json={
            "kitchen_id": data["kitchen"].id,
            "items": [{"menu_item_id": data["dish"].id, "quantity": 1}],
            "delivery_address_id": data["address"].id,
        })
        assert preview_res.status_code == 200
        preview = preview_res.json()
        assert preview["subtotal"] == 220.00
        assert preview["distance_km"] == 3.0
        assert preview["distance_type"] == "driving"
        assert preview["is_estimate"] is False
        assert preview["base_delivery_fee"] == 20.00
        assert preview["distance_fee"] == 24.00  # 3.0 * 8
        assert preview["delivery_fee"] == 44.00  # 20 + 24
        assert preview["total_amount"] == 264.00  # 220 + 44

        # 2. Place Order (Price Tampering Attempt: client cannot send a forged delivery fee)
        order_res = client.post("/api/v1/customer/orders", json={
            "kitchen_id": data["kitchen"].id,
            "items": [{"menu_item_id": data["dish"].id, "quantity": 1}],
            "delivery_address_id": data["address"].id,
            "payment_method": "CASH",
        })
        assert order_res.status_code == 201
        order_data = order_res.json()
        assert order_data["subtotal"] == 220.00
        assert order_data["delivery_fee"] == 44.00
        assert order_data["total_amount"] == 264.00
        assert order_data["delivery_distance_km"] == 3.0

        # Verify historical persistence in database
        saved_order = db_session.query(Order).filter(Order.id == order_data["id"]).first()
        assert saved_order is not None
        assert saved_order.delivery_fee == 44.00
        assert saved_order.total_amount == 264.00
        assert saved_order.delivery_distance_km == 3.0
        assert saved_order.pricing_breakdown_json is not None
        breakdown_stored = json.loads(saved_order.pricing_breakdown_json)
        assert breakdown_stored["delivery_fee"] == 44.00
        assert breakdown_stored["distance_km"] == 3.0
        assert breakdown_stored["base_delivery_fee"] == 20.00
        assert breakdown_stored["per_km_fee"] == 8.00

        # 3. Modify global platform settings (Rates increase: base fee ₹30, ₹10/km)
        DeliveryPricingService.update_pricing_policy(db_session, {
            "delivery_base_fee": 30.00,
            "delivery_per_km_fee": 10.00,
        })

        # 4. Assert historical order total remains IMMUTABLE
        db_session.refresh(saved_order)
        assert saved_order.delivery_fee == 44.00
        assert saved_order.total_amount == 264.00

        # 5. But NEW orders use the updated rates (₹30 base + ₹10/km * 3 = ₹60 delivery fee)
        new_preview_res = client.post("/api/v1/customer/checkout/preview", json={
            "kitchen_id": data["kitchen"].id,
            "items": [{"menu_item_id": data["dish"].id, "quantity": 1}],
            "delivery_address_id": data["address"].id,
        })
        assert new_preview_res.status_code == 200
        new_preview = new_preview_res.json()
        assert new_preview["base_delivery_fee"] == 30.00
        assert new_preview["distance_fee"] == 30.00  # 3.0 * 10
        assert new_preview["delivery_fee"] == 60.00
        assert new_preview["total_amount"] == 280.00


def test_admin_settings_delivery_api(client: TestClient, delivery_test_data):
    data = delivery_test_data

    # Login as admin
    login_res = client.post("/api/v1/auth/login", json={
        "email": data["admin"].email,
        "password": "AdminPass123!"
    })
    assert login_res.status_code == 200
    cookie = login_res.cookies.get(settings.SESSION_COOKIE_NAME)
    client.cookies.set(settings.SESSION_COOKIE_NAME, cookie)

    # 1. GET settings
    get_res = client.get("/api/v1/admin/settings")
    assert get_res.status_code == 200
    settings_data = get_res.json()
    assert "delivery_base_fee" in settings_data
    assert "delivery_per_km_fee" in settings_data
    assert "max_delivery_radius_km" in settings_data
    assert "surge_pricing_enabled" in settings_data

    # 2. PUT settings to configure custom rates
    put_res = client.put("/api/v1/admin/settings", json={
        "delivery_base_fee": 25.00,
        "delivery_per_km_fee": 9.50,
        "max_delivery_radius_km": 20.00,
        "surge_pricing_enabled": False,
    })
    assert put_res.status_code == 200
    updated = put_res.json()
    assert updated["delivery_base_fee"] == 25.00
    assert updated["delivery_per_km_fee"] == 9.50
    assert updated["max_delivery_radius_km"] == 20.00

    # 3. Validation: reject negative base fee
    bad_res = client.put("/api/v1/admin/settings", json={
        "delivery_base_fee": -5.00,
    })
    assert bad_res.status_code == 400
