"""
Test Suite: Demand Center — Kitchen Demand & Geographic Demand Areas Separation
Validates:
1. Feature 1 (Kitchen Demand):
   - Correctly groups real production orders by kitchen_id for approved kitchens.
   - Calculates real order count, unique customers, revenue, and demand intensity.
   - Thresholds: HIGH (>=20), MEDIUM (5-19), LOW (<5).
   - Excludes test orders (is_test=True, TEST-%), cancelled/rejected/refunded orders.
   - Excludes unapproved kitchens.
2. Feature 2 (Geographic Demand Areas):
   - Aggregates by customer delivery addresses (postal code and city).
   - Normalizes city name casing and common abbreviations (e.g. Han/hanamkonda -> Hanamkonda).
   - Excludes orders without customer delivery addresses.
3. Feature 3 (Map Data):
   - Returns kitchens with demand intensity and valid coordinates.
"""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.database import Base
from backend.app.models.user import User, KitchenProfile, Address
from backend.app.models.order import Order, OrderItem
from backend.app.models.menu import MenuItem
from backend.app.models.enums import UserRole, OrderStatus, PaymentStatus
from backend.app.api.routes.ml_forecast import get_demand_center


@pytest.fixture
def demand_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # 1. Create Kitchen Owners & Kitchens
    owner1 = User(
        id=str(uuid.uuid4()),
        email="owner1_demand@example.com",
        hashed_password="hash",
        full_name="Owner One",
        role=UserRole.KITCHEN_OWNER,
        is_active=True,
        is_verified=True,
    )
    owner2 = User(
        id=str(uuid.uuid4()),
        email="owner2_demand@example.com",
        hashed_password="hash",
        full_name="Owner Two",
        role=UserRole.KITCHEN_OWNER,
        is_active=True,
        is_verified=True,
    )
    unapproved_owner = User(
        id=str(uuid.uuid4()),
        email="unapproved_demand@example.com",
        hashed_password="hash",
        full_name="Unapproved Owner",
        role=UserRole.KITCHEN_OWNER,
        is_active=True,
        is_verified=True,
    )
    db.add_all([owner1, owner2, unapproved_owner])
    db.commit()

    kitchen1 = KitchenProfile(
        id=str(uuid.uuid4()),
        user_id=owner1.id,
        kitchen_name="VENGALA SONY's Kitchen",
        address="Bhavani nagar",
        city="Hanamkonda",
        latitude=18.004892,
        longitude=79.543196,
        is_open=True,
        is_approved=True,
    )
    kitchen2 = KitchenProfile(
        id=str(uuid.uuid4()),
        user_id=owner2.id,
        kitchen_name="Secondary Hub",
        address="Subedari",
        city="Hanamkonda",
        latitude=18.010000,
        longitude=79.550000,
        is_open=True,
        is_approved=True,
    )
    unapproved_kitchen = KitchenProfile(
        id=str(uuid.uuid4()),
        user_id=unapproved_owner.id,
        kitchen_name="Unapproved Kitchen",
        address="123 Street",
        city="Hanamkonda",
        latitude=18.020000,
        longitude=79.560000,
        is_open=False,
        is_approved=False,
    )
    db.add_all([kitchen1, kitchen2, unapproved_kitchen])
    db.commit()

    # 2. Customers and Addresses
    customer1 = User(
        id=str(uuid.uuid4()),
        email="cust1@example.com",
        hashed_password="hash",
        full_name="Customer One",
        role=UserRole.CUSTOMER,
        is_active=True,
        is_verified=True,
    )
    customer2 = User(
        id=str(uuid.uuid4()),
        email="cust2@example.com",
        hashed_password="hash",
        full_name="Customer Two",
        role=UserRole.CUSTOMER,
        is_active=True,
        is_verified=True,
    )
    db.add_all([customer1, customer2])
    db.commit()

    addr_han = Address(
        id=str(uuid.uuid4()),
        user_id=customer1.id,
        address_line1="Bhavani nagar",
        city="Han",  # Abbreviated city
        state="Telangana",
        postal_code="506001",
        latitude=18.005000,
        longitude=79.544000,
        is_default=True,
    )
    addr_hanamkonda = Address(
        id=str(uuid.uuid4()),
        user_id=customer2.id,
        address_line1="Ram Nagar",
        city="hanamkonda",  # Lowercase city
        state="Telangana",
        postal_code="506001",
        latitude=18.006815,
        longitude=79.557315,
        is_default=True,
    )
    db.add_all([addr_han, addr_hanamkonda])
    db.commit()

    # 3. Create real delivered orders for Kitchen 1
    now = datetime.now(timezone.utc)
    for i in range(6):  # 6 real orders -> MEDIUM demand intensity (5-19)
        ord_obj = Order(
            id=str(uuid.uuid4()),
            order_number=f"ORD-REAL-00{i+1}",
            customer_id=customer1.id if i < 4 else customer2.id,
            kitchen_id=kitchen1.id,
            delivery_address_id=addr_han.id if i < 4 else addr_hanamkonda.id,
            status=OrderStatus.DELIVERED,
            payment_status=PaymentStatus.SUCCESS,
            subtotal=250.0,
            total_amount=250.0,
            is_test=False,
            created_at=now - timedelta(days=2),
        )
        db.add(ord_obj)

    # 4. Create real delivered orders for Kitchen 2 (2 orders -> LOW demand intensity <5)
    for i in range(2):
        ord_obj = Order(
            id=str(uuid.uuid4()),
            order_number=f"ORD-K2-00{i+1}",
            customer_id=customer2.id,
            kitchen_id=kitchen2.id,
            delivery_address_id=addr_hanamkonda.id,
            status=OrderStatus.DELIVERED,
            payment_status=PaymentStatus.SUCCESS,
            subtotal=300.0,
            total_amount=300.0,
            is_test=False,
            created_at=now - timedelta(days=1),
        )
        db.add(ord_obj)

    # 5. Create Test Orders (MUST BE EXCLUDED)
    for i in range(5):
        ord_test = Order(
            id=str(uuid.uuid4()),
            order_number=f"TEST-ORD-00{i+1}",
            customer_id=customer1.id,
            kitchen_id=kitchen1.id,
            delivery_address_id=None,
            status=OrderStatus.DELIVERED,
            payment_status=PaymentStatus.SUCCESS,
            subtotal=500.0,
            total_amount=500.0,
            is_test=True,
            created_at=now - timedelta(days=3),
        )
        db.add(ord_test)

    # 6. Create Cancelled Orders (MUST BE EXCLUDED)
    ord_cancelled = Order(
        id=str(uuid.uuid4()),
        order_number="ORD-CANCELLED-001",
        customer_id=customer1.id,
        kitchen_id=kitchen1.id,
        delivery_address_id=addr_han.id,
        status=OrderStatus.CANCELLED,
        payment_status=PaymentStatus.REFUNDED,
        subtotal=400.0,
        total_amount=400.0,
        is_test=False,
        created_at=now - timedelta(days=1),
    )
    db.add(ord_cancelled)

    db.commit()

    yield {
        "db": db,
        "owner1": owner1,
        "kitchen1": kitchen1,
        "kitchen2": kitchen2,
        "unapproved_kitchen": unapproved_kitchen,
    }

    db.close()


def test_kitchen_demand_and_geographic_demand_separation(demand_db):
    """Verify Feature 1 (Kitchen Demand) and Feature 2 (Geographic Demand) are separated and accurate."""
    db = demand_db["db"]
    owner1 = demand_db["owner1"]
    k1 = demand_db["kitchen1"]
    k2 = demand_db["kitchen2"]

    res = get_demand_center(days=30, kitchen_id=None, db=db, current_user=owner1)

    assert res["status"] == "operational"
    # Total real orders: 6 (kitchen 1) + 2 (kitchen 2) = 8. (Test orders and cancelled orders excluded!)
    assert res["total_orders"] == 8
    # Total real revenue: 6 * 250 (1500) + 2 * 300 (600) = 2100.0
    assert res["total_revenue"] == 2100.0

    # 1. Feature 1 — Kitchen Demand
    kitchen_demand = res["kitchen_demand"]
    assert len(kitchen_demand) == 2  # Only 2 approved kitchens (unapproved excluded)

    # Kitchen 1 should be first (most orders: 6)
    k1_demand = next(kd for kd in kitchen_demand if kd["kitchen_id"] == k1.id)
    assert k1_demand["kitchen_name"] == "VENGALA SONY's Kitchen"
    assert k1_demand["order_count"] == 6
    assert k1_demand["unique_customers"] == 2
    assert k1_demand["revenue"] == 1500.0
    assert k1_demand["demand_intensity"] == "MEDIUM"  # 5-19 real orders is MEDIUM
    assert k1_demand["is_my_kitchen"] is True

    # Kitchen 2 should have 2 orders -> LOW (<5)
    k2_demand = next(kd for kd in kitchen_demand if kd["kitchen_id"] == k2.id)
    assert k2_demand["kitchen_name"] == "Secondary Hub"
    assert k2_demand["order_count"] == 2
    assert k2_demand["revenue"] == 600.0
    assert k2_demand["demand_intensity"] == "LOW"

    # 2. Feature 2 — Geographic Demand Areas
    demand_areas = res["demand_areas"]
    # Both "Han — 506001" and "hanamkonda — 506001" should normalize to "Hanamkonda — 506001"!
    assert len(demand_areas) == 1
    area = demand_areas[0]
    assert area["area_name"] == "Hanamkonda — 506001"
    assert area["city"] == "Hanamkonda"
    assert area["order_count"] == 8
    assert area["unique_customers"] == 2
    assert area["revenue"] == 2100.0
    assert area["demand_intensity"] == "MEDIUM"

    # 3. Feature 3 — Map Kitchens
    cloudkitchen_kitchens = res["cloudkitchen_kitchens"]
    assert len(cloudkitchen_kitchens) == 2
    ck1 = next(k for k in cloudkitchen_kitchens if k["id"] == k1.id)
    assert ck1["demand_intensity"] == "MEDIUM"
    assert ck1["order_count"] == 6
    assert ck1["latitude"] == 18.004892
    assert ck1["longitude"] == 79.543196
