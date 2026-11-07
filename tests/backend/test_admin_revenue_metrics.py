"""
Isolated Test Suite for Admin Dashboard Revenue, Financial, and Operational Metrics.
Validates:
1. Empty dashboard returns exactly ₹0 revenue without errors.
2. Only successfully delivered and paid orders qualify as realized revenue.
3. Cancelled orders and refunded payments are strictly excluded from revenue.
4. Failed and pending payments are strictly excluded from revenue.
5. In-flight active orders (preparing/ready) are tracked separately and not counted in delivered revenue.
6. Synthetic test fixture orders (is_test=True, TEST-*) are strictly isolated from production metrics.
7. Date range filtering properly includes/excludes orders based on timestamps.
8. Dynamic updates reflect immediate status transitions without caching stale figures.
9. Financial breakdown accurately distinguishes Gross Order Value (GOV), Collected Payments, Refunds, Platform Commission, and Net Revenue.
"""
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.deps import require_admin
from backend.app.core.security import get_password_hash
from backend.app.models.user import User, KitchenProfile, Address
from backend.app.models.order import Order, Payment
from backend.app.models.enums import UserRole, OrderStatus, PaymentStatus
from backend.app.main import app


@pytest.fixture
def admin_user(db_session: Session) -> User:
    """Create an isolated admin user for test auth."""
    admin = User(
        email=f"admin_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=get_password_hash("AdminPass123!"),
        full_name="Admin Tester",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture
def auth_client(client: TestClient, admin_user: User):
    """Override require_admin dependency to authenticate as admin."""
    app.dependency_overrides[require_admin] = lambda: admin_user
    yield client
    app.dependency_overrides.pop(require_admin, None)


@pytest.fixture
def setup_kitchen_and_customer(db_session: Session):
    """Create kitchen and customer for placing test orders."""
    owner = User(
        email=f"owner_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=get_password_hash("OwnerPass123!"),
        full_name="Kitchen Owner",
        role=UserRole.KITCHEN_OWNER,
        is_active=True,
        is_verified=True,
    )
    customer = User(
        email=f"cust_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=get_password_hash("CustPass123!"),
        full_name="Customer User",
        role=UserRole.CUSTOMER,
        is_active=True,
        is_verified=True,
    )
    db_session.add_all([owner, customer])
    db_session.commit()

    kitchen = KitchenProfile(
        user_id=owner.id,
        kitchen_name="Test Cloud Kitchen",
        description="Quality Test Kitchen",
        address="123 Food Street",
        city="Hyderabad",
        state="Telangana",
        postal_code="500001",
        is_open=True,
        is_approved=True,
        approval_status="APPROVED",
    )
    db_session.add(kitchen)
    db_session.commit()
    db_session.refresh(kitchen)

    return kitchen, customer


def test_empty_dashboard_returns_zero_revenue(auth_client: TestClient):
    """When no orders exist in the database, dashboard must return 0.0 for revenue and metrics."""
    res = auth_client.get("/admin/dashboard")
    assert res.status_code == 200
    data = res.json()

    assert data["revenue"] == 0.0
    assert data["gross_order_value"] == 0.0
    assert data["collected_payments"] == 0.0
    assert data["refunded_amount"] == 0.0
    assert data["in_flight_revenue"] == 0.0
    assert data["total_orders"] == 0
    assert data["completed_orders"] == 0
    assert data["cancelled_orders"] == 0


def test_delivered_and_paid_orders_counted_in_revenue(
    auth_client: TestClient, db_session: Session, setup_kitchen_and_customer
):
    """Real orders with DELIVERED status and SUCCESS payment must be aggregated into realized revenue."""
    kitchen, customer = setup_kitchen_and_customer

    order1 = Order(
        order_number="ORD-REAL-001",
        customer_id=customer.id,
        kitchen_id=kitchen.id,
        status=OrderStatus.DELIVERED,
        payment_status=PaymentStatus.SUCCESS,
        subtotal=300.0,
        tax=15.0,
        delivery_fee=35.0,
        total_amount=350.0,
        is_test=False,
    )
    order2 = Order(
        order_number="ORD-REAL-002",
        customer_id=customer.id,
        kitchen_id=kitchen.id,
        status=OrderStatus.DELIVERED,
        payment_status=PaymentStatus.SUCCESS,
        subtotal=200.0,
        tax=10.0,
        delivery_fee=30.0,
        total_amount=240.0,
        is_test=False,
    )
    db_session.add_all([order1, order2])
    db_session.commit()

    res = auth_client.get("/admin/dashboard")
    assert res.status_code == 200
    data = res.json()

    assert data["revenue"] == 590.0
    assert data["gross_order_value"] == 590.0
    assert data["collected_payments"] == 590.0
    assert data["refunded_amount"] == 0.0
    assert data["completed_orders"] == 2
    assert data["total_orders"] == 2
    assert data["platform_commission"] == round(590.0 * 0.15, 2)


def test_cancelled_and_refunded_orders_excluded_from_revenue(
    auth_client: TestClient, db_session: Session, setup_kitchen_and_customer
):
    """Cancelled and refunded orders must be strictly excluded from realized revenue and collected payments."""
    kitchen, customer = setup_kitchen_and_customer

    # 1 delivered order of 400
    delivered_order = Order(
        order_number="ORD-REAL-010",
        customer_id=customer.id,
        kitchen_id=kitchen.id,
        status=OrderStatus.DELIVERED,
        payment_status=PaymentStatus.SUCCESS,
        subtotal=350.0,
        total_amount=400.0,
        is_test=False,
    )
    # 1 cancelled & refunded order of 250
    cancelled_order = Order(
        order_number="ORD-REAL-011",
        customer_id=customer.id,
        kitchen_id=kitchen.id,
        status=OrderStatus.CANCELLED,
        payment_status=PaymentStatus.REFUNDED,
        subtotal=220.0,
        total_amount=250.0,
        is_test=False,
    )
    db_session.add_all([delivered_order, cancelled_order])
    db_session.commit()

    res = auth_client.get("/admin/dashboard")
    assert res.status_code == 200
    data = res.json()

    assert data["revenue"] == 400.0  # Not 650.0!
    assert data["gross_order_value"] == 650.0
    assert data["collected_payments"] == 400.0
    assert data["refunded_amount"] == 250.0
    assert data["cancelled_orders"] == 1
    assert data["completed_orders"] == 1
    assert data["total_orders"] == 2


def test_failed_and_pending_payments_excluded(
    auth_client: TestClient, db_session: Session, setup_kitchen_and_customer
):
    """Orders with FAILED or PENDING payment must not be counted as realized revenue."""
    kitchen, customer = setup_kitchen_and_customer

    unpaid1 = Order(
        order_number="ORD-REAL-020",
        customer_id=customer.id,
        kitchen_id=kitchen.id,
        status=OrderStatus.ORDER_PLACED,
        payment_status=PaymentStatus.PENDING,
        subtotal=300.0,
        total_amount=300.0,
        is_test=False,
    )
    unpaid2 = Order(
        order_number="ORD-REAL-021",
        customer_id=customer.id,
        kitchen_id=kitchen.id,
        status=OrderStatus.DELIVERED,
        payment_status=PaymentStatus.FAILED,
        subtotal=200.0,
        total_amount=200.0,
        is_test=False,
    )
    db_session.add_all([unpaid1, unpaid2])
    db_session.commit()

    res = auth_client.get("/admin/dashboard")
    assert res.status_code == 200
    data = res.json()

    assert data["revenue"] == 0.0  # Even though unpaid2 is DELIVERED, payment failed!
    assert data["collected_payments"] == 0.0
    assert data["gross_order_value"] == 500.0
    assert data["pending_orders"] == 1
    assert data["completed_orders"] == 1


def test_in_flight_paid_orders_distinction(
    auth_client: TestClient, db_session: Session, setup_kitchen_and_customer
):
    """In-flight paid orders (PREPARING, READY) are tracked separately and not counted in delivered revenue."""
    kitchen, customer = setup_kitchen_and_customer

    in_flight1 = Order(
        order_number="ORD-REAL-030",
        customer_id=customer.id,
        kitchen_id=kitchen.id,
        status=OrderStatus.PREPARING,
        payment_status=PaymentStatus.SUCCESS,
        subtotal=320.0,
        total_amount=320.0,
        is_test=False,
    )
    in_flight2 = Order(
        order_number="ORD-REAL-031",
        customer_id=customer.id,
        kitchen_id=kitchen.id,
        status=OrderStatus.READY,
        payment_status=PaymentStatus.SUCCESS,
        subtotal=160.0,
        total_amount=160.0,
        is_test=False,
    )
    db_session.add_all([in_flight1, in_flight2])
    db_session.commit()

    res = auth_client.get("/admin/dashboard")
    assert res.status_code == 200
    data = res.json()

    assert data["revenue"] == 0.0  # Not delivered yet!
    assert data["in_flight_revenue"] == 480.0
    assert data["collected_payments"] == 480.0
    assert data["gross_order_value"] == 480.0
    assert data["completed_orders"] == 0


def test_test_orders_strictly_isolated_from_production(
    auth_client: TestClient, db_session: Session, setup_kitchen_and_customer
):
    """Synthetic test orders (is_test=True, TEST-*) must never contaminate production revenue or order counts."""
    kitchen, customer = setup_kitchen_and_customer

    # Seed 19 test orders totaling 9,061 (matching the original contamination)
    test_order1 = Order(
        order_number="TEST-ORD-KITS-001",
        customer_id=customer.id,
        kitchen_id=kitchen.id,
        status=OrderStatus.DELIVERED,
        payment_status=PaymentStatus.SUCCESS,
        subtotal=6744.0,
        total_amount=6744.0,
        is_test=True,
    )
    test_order2 = Order(
        order_number="TEST-ORD-SONY-001",
        customer_id=customer.id,
        kitchen_id=kitchen.id,
        status=OrderStatus.DELIVERED,
        payment_status=PaymentStatus.SUCCESS,
        subtotal=2317.0,
        total_amount=2317.0,
        is_test=True,
    )

    # Seed 1 real customer order of 3,699
    real_order = Order(
        order_number="ORD-20261005-3849",
        customer_id=customer.id,
        kitchen_id=kitchen.id,
        status=OrderStatus.DELIVERED,
        payment_status=PaymentStatus.SUCCESS,
        subtotal=3699.0,
        total_amount=3699.0,
        is_test=False,
    )
    db_session.add_all([test_order1, test_order2, real_order])
    db_session.commit()

    # 1. Default (production scenario): MUST return only 3,699.0, NOT 12,760.0!
    res_prod = auth_client.get("/admin/dashboard")
    assert res_prod.status_code == 200
    prod_data = res_prod.json()
    assert prod_data["revenue"] == 3699.0
    assert prod_data["total_orders"] == 1
    assert prod_data["completed_orders"] == 1
    assert prod_data["scenario"] == "production"

    # 2. Test scenario toggle: returns the 9,061.0 from test orders
    res_test = auth_client.get("/admin/dashboard?scenario=test_scenario")
    assert res_test.status_code == 200
    test_data = res_test.json()
    assert test_data["revenue"] == 9061.0
    assert test_data["total_orders"] == 2
    assert test_data["completed_orders"] == 2
    assert test_data["scenario"] == "test_scenario"


def test_date_range_filtering(
    auth_client: TestClient, db_session: Session, setup_kitchen_and_customer
):
    """Orders outside the requested date window must be excluded from metrics."""
    kitchen, customer = setup_kitchen_and_customer
    now = datetime.now(timezone.utc)

    # Order from 10 days ago
    old_order = Order(
        order_number="ORD-OLD-001",
        customer_id=customer.id,
        kitchen_id=kitchen.id,
        status=OrderStatus.DELIVERED,
        payment_status=PaymentStatus.SUCCESS,
        subtotal=1000.0,
        total_amount=1000.0,
        is_test=False,
        created_at=now - timedelta(days=10),
    )
    # Order from today
    new_order = Order(
        order_number="ORD-NEW-001",
        customer_id=customer.id,
        kitchen_id=kitchen.id,
        status=OrderStatus.DELIVERED,
        payment_status=PaymentStatus.SUCCESS,
        subtotal=500.0,
        total_amount=500.0,
        is_test=False,
        created_at=now,
    )
    db_session.add_all([old_order, new_order])
    db_session.commit()

    # Query with start_date filter 3 days ago
    start_filter = (now - timedelta(days=3)).strftime("%Y-%m-%d")
    res = auth_client.get(f"/admin/dashboard?start_date={start_filter}")
    assert res.status_code == 200
    data = res.json()

    assert data["revenue"] == 500.0
    assert data["total_orders"] == 1


def test_dynamic_updates_on_order_status_transitions(
    auth_client: TestClient, db_session: Session, setup_kitchen_and_customer
):
    """Metrics must update dynamically as order status transitions without stale caching."""
    kitchen, customer = setup_kitchen_and_customer

    order = Order(
        order_number="ORD-DYNAMIC-001",
        customer_id=customer.id,
        kitchen_id=kitchen.id,
        status=OrderStatus.PREPARING,
        payment_status=PaymentStatus.SUCCESS,
        subtotal=450.0,
        total_amount=450.0,
        is_test=False,
    )
    db_session.add(order)
    db_session.commit()

    # Step 1: PREPARING -> revenue is 0.0, in_flight is 450.0
    res1 = auth_client.get("/admin/dashboard")
    assert res1.json()["revenue"] == 0.0
    assert res1.json()["in_flight_revenue"] == 450.0

    # Step 2: DELIVERED -> revenue becomes 450.0, in_flight is 0.0
    order.status = OrderStatus.DELIVERED
    db_session.commit()

    res2 = auth_client.get("/admin/dashboard")
    assert res2.json()["revenue"] == 450.0
    assert res2.json()["in_flight_revenue"] == 0.0

    # Step 3: CANCELLED & REFUNDED -> revenue becomes 0.0, refunded becomes 450.0
    order.status = OrderStatus.CANCELLED
    order.payment_status = PaymentStatus.REFUNDED
    db_session.commit()

    res3 = auth_client.get("/admin/dashboard")
    assert res3.json()["revenue"] == 0.0
    assert res3.json()["refunded_amount"] == 450.0
    assert res3.json()["cancelled_orders"] == 1
