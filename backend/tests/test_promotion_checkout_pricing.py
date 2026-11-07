"""
Comprehensive Verification Test for Customer Promotion Discount Checkout & Payment Flow

Tests the EXACT user scenario:
- Subtotal = ₹900
- Coupon: WELCOME_20 (20% discount)
- Expected:
    Discount = ₹180.0
    Final = ₹720.0
- Verifies:
    1. Checkout Preview = ₹720.0
    2. Payment record = ₹720.0 (NOT ₹900.0)
    3. Created Order = ₹720.0 (persisting subtotal=900, discount=180, promotion_code="WELCOME_20")
    4. Customer Order History = ₹720.0
    5. Admin Order Details = ₹720.0 (and payment.amount = ₹720.0)
- Tests coupon removal:
    Subtotal = ₹900.0
    Discount = ₹0.0
    Final = ₹900.0
    Payment = ₹900.0
"""

import pytest
import uuid
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.core.database import Base
from app.models import User, KitchenProfile, MenuItem, Promotion, Order, Payment
from app.models.enums import UserRole, OrderStatus, PaymentStatus
from app.schemas.customer import CheckoutPreviewRequest, OrderCreateRequest, CartItemRequest
from app.services.customer_service import CustomerService


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    db = TestingSession()

    # Create admin
    admin = User(
        id=str(uuid.uuid4()),
        email="admin@test.com",
        hashed_password="hash",
        full_name="Admin User",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    # Create customer
    customer = User(
        id=str(uuid.uuid4()),
        email="customer@test.com",
        hashed_password="hash",
        full_name="Customer User",
        role=UserRole.CUSTOMER,
        is_active=True,
        is_verified=True,
    )
    # Create kitchen owner & profile
    owner = User(
        id=str(uuid.uuid4()),
        email="owner@test.com",
        hashed_password="hash",
        full_name="Kitchen Owner",
        role=UserRole.KITCHEN_OWNER,
        is_active=True,
        is_verified=True,
    )
    db.add_all([admin, customer, owner])
    db.commit()

    kitchen = KitchenProfile(
        id=str(uuid.uuid4()),
        user_id=owner.id,
        kitchen_name="Gourmet Cloud Kitchen",
        address="123 Food Street, Indiranagar",
        city="Bangalore",
        is_open=True,
        is_approved=True,
    )
    db.add(kitchen)
    db.commit()

    # Create menu item: ₹450 price
    item = MenuItem(
        id=str(uuid.uuid4()),
        kitchen_id=kitchen.id,
        name="Truffle Pizza",
        category="Pizza",
        cuisine="Italian",
        price=450.0,
        is_available=True,
    )
    db.add(item)

    # Create promotion: WELCOME_20 (20% discount, min order 300, max discount 200, per user limit 2)
    promo = Promotion(
        id=str(uuid.uuid4()),
        code="WELCOME_20",
        title="Welcome 20% Off",
        description="20% off welcome coupon",
        discount_percentage=20.0,
        minimum_order_amount=300.0,
        max_discount_amount=200.0,
        is_active=True,
        usage_count=0,
        per_user_limit=2,
    )
    db.add(promo)
    db.commit()

    yield {
        "db": db,
        "customer": customer,
        "kitchen": kitchen,
        "item": item,
        "promo": promo,
    }

    db.close()


def test_promotion_discount_exact_scenario(test_db):
    """
    Subtotal = ₹900 (2 items @ ₹450)
    Coupon = WELCOME_20
    Discount = ₹180 (20% of 900)
    Final Payable = ₹720
    """
    db = test_db["db"]
    customer = test_db["customer"]
    kitchen = test_db["kitchen"]
    item = test_db["item"]

    # 1. Checkout Preview with coupon
    preview_req = CheckoutPreviewRequest(
        kitchen_id=kitchen.id,
        items=[CartItemRequest(menu_item_id=item.id, quantity=2)],
        promotion_code="WELCOME_20",
    )
    preview = CustomerService.calculate_checkout_preview(db, preview_req, customer)

    assert preview.subtotal == 900.0
    assert preview.discount_amount == 180.0
    assert preview.applied_promotion_code == "WELCOME_20"
    assert preview.total_amount == 720.0, f"Expected final total 720.0, got {preview.total_amount}"

    # 2. Place Order with coupon
    order_req = OrderCreateRequest(
        kitchen_id=kitchen.id,
        items=[CartItemRequest(menu_item_id=item.id, quantity=2)],
        payment_method="UPI",
        promotion_code="WELCOME_20",
    )
    order = CustomerService.place_order(db, customer, order_req)
    db.commit()

    # 3. Verify Created Order persistence
    assert order.subtotal == 900.0
    assert order.discount_amount == 180.0
    assert order.promotion_code == "WELCOME_20"
    assert order.total_amount == 720.0

    # 4. Verify Payment record created with exact discounted amount
    payment = db.query(Payment).filter(Payment.order_id == order.id).first()
    assert payment is not None
    assert payment.amount == 720.0, f"Payment amount MUST be ₹720, got {payment.amount}"
    assert payment.status == PaymentStatus.SUCCESS

    # 5. Verify Customer Order History retrieval preserves exact discount & total
    orders = CustomerService.get_customer_orders(db, customer.id)
    assert len(orders) == 1
    o_hist = orders[0]
    assert o_hist.subtotal == 900.0
    assert o_hist.discount_amount == 180.0
    assert o_hist.promotion_code == "WELCOME_20"
    assert o_hist.total_amount == 720.0

    # 6. Verify Admin Order query view matches exact total
    persisted_order = db.query(Order).filter(Order.id == order.id).first()
    assert persisted_order.total_amount == 720.0
    assert persisted_order.payments[0].amount == 720.0


def test_coupon_removal_returns_to_undiscounted_amount(test_db):
    """
    When coupon is removed:
    Subtotal = ₹900
    Discount = ₹0
    Final = ₹900
    Payment = ₹900
    """
    db = test_db["db"]
    customer = test_db["customer"]
    kitchen = test_db["kitchen"]
    item = test_db["item"]

    # 1. Preview without coupon
    preview_req = CheckoutPreviewRequest(
        kitchen_id=kitchen.id,
        items=[CartItemRequest(menu_item_id=item.id, quantity=2)],
        promotion_code=None,
    )
    preview = CustomerService.calculate_checkout_preview(db, preview_req, customer)

    assert preview.subtotal == 900.0
    assert preview.discount_amount == 0.0
    assert preview.applied_promotion_code is None
    assert preview.total_amount == 900.0

    # 2. Place Order without coupon
    order_req = OrderCreateRequest(
        kitchen_id=kitchen.id,
        items=[CartItemRequest(menu_item_id=item.id, quantity=2)],
        payment_method="CASH_ON_DELIVERY",
        promotion_code=None,
    )
    order = CustomerService.place_order(db, customer, order_req)
    db.commit()

    assert order.subtotal == 900.0
    assert order.discount_amount == 0.0
    assert order.promotion_code is None
    assert order.total_amount == 900.0

    payment = db.query(Payment).filter(Payment.order_id == order.id).first()
    assert payment is not None
    assert payment.amount == 900.0, f"Undiscounted payment must be ₹900, got {payment.amount}"
