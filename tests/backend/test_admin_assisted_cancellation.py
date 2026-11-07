"""
Focused Automated Test Suite for Admin-Assisted Order Cancellation for READY Orders.
Validates all 24 required scenarios:
 1. READY -> request cancellation succeeds
 2. READY -> direct cancellation still fails (server-side protection intact)
 3. Duplicate pending request fails
 4. Customer cannot request another customer's order (403)
 5. Admin can view request
 6. Kitchen Owner gets 403 on admin cancellation routes
 7. Customer cannot access admin endpoint (403)
 8. Admin approve succeeds
 9. Order becomes CANCELLED upon approval
10. Request becomes APPROVED upon approval
11. Wastage uses actual recipe
12. WASTE inventory ledger created
13. Duplicate approval cannot duplicate wastage
14. Admin reject succeeds
15. Order remains READY after rejection
16. Rejection creates no wastage
17. Rejection creates no WASTE ledger
18. Customer receives approval notification
19. Customer receives rejection notification
20. OUT_FOR_DELIVERY request rejected
21. DELIVERED request rejected
22. CANCELLED request rejected
23. Repeated approval safely rejected/idempotent
24. Repeated rejection safely rejected/idempotent
"""
import uuid
import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.security import get_password_hash
from backend.app.models.user import User, Address, KitchenProfile
from backend.app.models.enums import UserRole, OrderStatus, PaymentStatus, InventoryTransactionType
from backend.app.models.menu import MenuItem, Ingredient, MenuItemIngredient
from backend.app.models.order import Order, OrderItem, CancellationRequest
from backend.app.models.inventory import WasteRecord, InventoryTransaction, Purchase, Inventory
from backend.app.models.platform import Notification


# ── Synthetic Data Fixtures & Helpers ────────────────────────────────────────

def _create_user(db: Session, email_prefix: str, role: UserRole, password: str = "TestPass123!") -> User:
    user = User(
        email=f"{email_prefix}_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=get_password_hash(password),
        full_name=f"Test {role.value.capitalize()}",
        role=role,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_kitchen(db: Session, email_prefix: str) -> tuple[User, KitchenProfile]:
    user = _create_user(db, email_prefix, UserRole.KITCHEN_OWNER)
    kitchen = KitchenProfile(
        user_id=user.id,
        kitchen_name="Biryani Express Kitchen",
        description="Authentic Dum Biryani Cloud Kitchen",
        address="100 Commercial Street",
        city="Bangalore",
        state="Karnataka",
        postal_code="560001",
        phone="+919876543210",
        latitude=12.9716,
        longitude=77.5946,
        is_open=True,
        is_approved=True,
        approval_status="APPROVED",
    )
    db.add(kitchen)
    db.commit()
    db.refresh(kitchen)
    return user, kitchen


def _create_customer_with_address(db: Session, email_prefix: str) -> tuple[User, Address]:
    user = _create_user(db, email_prefix, UserRole.CUSTOMER)
    address = Address(
        user_id=user.id,
        address_line1="Flat 204, Green Meadows",
        city="Bangalore",
        state="Karnataka",
        postal_code="560034",
        latitude=12.9352,
        longitude=77.6245,
        is_default=True,
    )
    db.add(address)
    db.commit()
    db.refresh(address)
    return user, address


def _setup_recipe(db: Session, kitchen_id: str):
    # Ingredients: Basmati Rice (0.20 kg), Chicken (0.18 kg), Cooking Oil (0.02 L)
    rice = Ingredient(
        kitchen_id=kitchen_id,
        name="Basmati Rice",
        unit="kg",
        current_stock=20.0,
        minimum_stock_threshold=2.0,
        reorder_quantity=20.0,
    )
    chicken = Ingredient(
        kitchen_id=kitchen_id,
        name="Fresh Chicken",
        unit="kg",
        current_stock=20.0,
        minimum_stock_threshold=2.0,
        reorder_quantity=20.0,
    )
    oil = Ingredient(
        kitchen_id=kitchen_id,
        name="Cooking Oil",
        unit="L",
        current_stock=20.0,
        minimum_stock_threshold=2.0,
        reorder_quantity=20.0,
    )
    db.add_all([rice, chicken, oil])
    db.commit()

    # Purchases to establish unit costs: ₹60/kg rice, ₹200/kg chicken, ₹120/L oil
    p_rice = Purchase(kitchen_id=kitchen_id, ingredient_id=rice.id, supplier_name="Metro Cash", unit="kg", quantity=10.0, unit_cost=60.0, total_cost=600.0)
    p_chicken = Purchase(kitchen_id=kitchen_id, ingredient_id=chicken.id, supplier_name="Fresh Farm", unit="kg", quantity=10.0, unit_cost=200.0, total_cost=2000.0)
    p_oil = Purchase(kitchen_id=kitchen_id, ingredient_id=oil.id, supplier_name="Fortune Oil", unit="L", quantity=10.0, unit_cost=120.0, total_cost=1200.0)
    db.add_all([p_rice, p_chicken, p_oil])
    db.commit()

    menu_item = MenuItem(
        kitchen_id=kitchen_id,
        name="Special Chicken Biryani",
        category="Biryani",
        cuisine="Mughlai",
        price=300.0,
        is_available=True,
        is_veg=False,
    )
    db.add(menu_item)
    db.commit()

    # Recipe
    r1 = MenuItemIngredient(menu_item_id=menu_item.id, ingredient_id=rice.id, quantity_required=0.20)
    r2 = MenuItemIngredient(menu_item_id=menu_item.id, ingredient_id=chicken.id, quantity_required=0.18)
    r3 = MenuItemIngredient(menu_item_id=menu_item.id, ingredient_id=oil.id, quantity_required=0.02)
    db.add_all([r1, r2, r3])
    db.commit()

    return menu_item, rice, chicken, oil


def _create_test_order(
    db: Session,
    customer_id: str,
    kitchen_id: str,
    menu_item: MenuItem,
    quantity: int = 2,
    status: OrderStatus = OrderStatus.READY,
) -> Order:
    order = Order(
        order_number=f"CK-{uuid.uuid4().hex[:6].upper()}",
        customer_id=customer_id,
        kitchen_id=kitchen_id,
        status=status,
        subtotal=menu_item.price * quantity,
        tax=menu_item.price * quantity * 0.05,
        delivery_fee=40.0,
        total_amount=(menu_item.price * quantity * 1.05) + 40.0,
        payment_status=PaymentStatus.SUCCESS,
        delivery_address_text="Flat 204, Green Meadows, Bangalore",
        delivery_latitude=12.9352,
        delivery_longitude=77.6245,
    )
    db.add(order)
    db.commit()

    item = OrderItem(
        order_id=order.id,
        menu_item_id=menu_item.id,
        item_name=menu_item.name,
        unit_price=menu_item.price,
        quantity=quantity,
        subtotal=menu_item.price * quantity,
    )
    db.add(item)
    db.commit()
    db.refresh(order)
    return order


def _login(client: TestClient, user: User, password: str = "TestPass123!"):
    resp = client.post("/api/v1/auth/login", json={"email": user.email, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    cookie = resp.cookies.get(settings.SESSION_COOKIE_NAME)
    client.cookies.set(settings.SESSION_COOKIE_NAME, cookie)
    return cookie


# ── Tests 1 & 2: READY order cancellation behaviors ─────────────────────────

def test_01_ready_order_request_cancellation_succeeds(client: TestClient, db_session: Session):
    """1. READY -> request cancellation succeeds (status 200, PENDING, order stays READY)."""
    _, kitchen = _create_kitchen(db_session, "ko_01")
    cust, _ = _create_customer_with_address(db_session, "cust_01")
    biryani, _, _, _ = _setup_recipe(db_session, kitchen.id)
    order = _create_test_order(db_session, cust.id, kitchen.id, biryani, quantity=2, status=OrderStatus.READY)

    _login(client, cust)
    resp = client.post(
        f"/api/v1/customer/orders/{order.id}/cancellation-request",
        json={"reason": "Changed my mind", "customer_note": "Guest cancelled visit"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "PENDING"
    assert data["order_id"] == order.id
    assert data["reason"] == "Changed my mind"
    assert data["customer_note"] == "Guest cancelled visit"

    # Verify order is still READY (did not directly cancel)
    db_session.refresh(order)
    assert order.status == OrderStatus.READY


def test_02_ready_order_direct_cancellation_still_fails(client: TestClient, db_session: Session):
    """2. READY -> direct cancellation still fails with HTTP 400 (server-side protection intact)."""
    _, kitchen = _create_kitchen(db_session, "ko_02")
    cust, _ = _create_customer_with_address(db_session, "cust_02")
    biryani, _, _, _ = _setup_recipe(db_session, kitchen.id)
    order = _create_test_order(db_session, cust.id, kitchen.id, biryani, status=OrderStatus.READY)

    _login(client, cust)
    resp = client.post(f"/api/v1/customer/orders/{order.id}/cancel?reason=Changed+mind")
    assert resp.status_code == 400
    assert "no longer available" in resp.json()["detail"].lower()

    # Order must remain READY
    db_session.refresh(order)
    assert order.status == OrderStatus.READY


# ── Test 3: Duplicate pending request rejected ───────────────────────────────

def test_03_duplicate_pending_request_fails(client: TestClient, db_session: Session):
    """3. Duplicate pending request fails with HTTP 400."""
    _, kitchen = _create_kitchen(db_session, "ko_03")
    cust, _ = _create_customer_with_address(db_session, "cust_03")
    biryani, _, _, _ = _setup_recipe(db_session, kitchen.id)
    order = _create_test_order(db_session, cust.id, kitchen.id, biryani, status=OrderStatus.READY)

    _login(client, cust)
    resp1 = client.post(
        f"/api/v1/customer/orders/{order.id}/cancellation-request",
        json={"reason": "Changed my mind"},
    )
    assert resp1.status_code == 200

    resp2 = client.post(
        f"/api/v1/customer/orders/{order.id}/cancellation-request",
        json={"reason": "Ordered by mistake"},
    )
    assert resp2.status_code == 400
    assert "already pending" in resp2.json()["detail"].lower()


# ── Test 4: Cannot request another customer's order ──────────────────────────

def test_04_customer_cannot_request_another_customers_order(client: TestClient, db_session: Session):
    """4. Customer cannot request another customer's order (HTTP 403)."""
    _, kitchen = _create_kitchen(db_session, "ko_04")
    cust1, _ = _create_customer_with_address(db_session, "cust_04a")
    cust2, _ = _create_customer_with_address(db_session, "cust_04b")
    biryani, _, _, _ = _setup_recipe(db_session, kitchen.id)
    order1 = _create_test_order(db_session, cust1.id, kitchen.id, biryani, status=OrderStatus.READY)

    # cust2 attempts to submit cancellation request for cust1's order
    _login(client, cust2)
    resp = client.post(
        f"/api/v1/customer/orders/{order1.id}/cancellation-request",
        json={"reason": "Unauthorized attempt"},
    )
    assert resp.status_code == 403


# ── Tests 5, 6, 7: Authorization on Admin endpoints ─────────────────────────

def test_05_admin_can_view_cancellation_requests(client: TestClient, db_session: Session):
    """5. Admin can view/list cancellation requests."""
    admin = _create_user(db_session, "admin_05", UserRole.ADMIN)
    _, kitchen = _create_kitchen(db_session, "ko_05")
    cust, _ = _create_customer_with_address(db_session, "cust_05")
    biryani, _, _, _ = _setup_recipe(db_session, kitchen.id)
    order = _create_test_order(db_session, cust.id, kitchen.id, biryani, status=OrderStatus.READY)

    # Customer submits request
    _login(client, cust)
    req_resp = client.post(
        f"/api/v1/customer/orders/{order.id}/cancellation-request",
        json={"reason": "Cannot receive the order", "customer_note": "Travelling out of town"},
    )
    assert req_resp.status_code == 200
    cr_id = req_resp.json()["id"]

    # Admin views list and single request detail
    _login(client, admin)
    list_resp = client.get("/api/v1/admin/cancellation-requests?status=PENDING")
    assert list_resp.status_code == 200
    requests = list_resp.json()
    assert any(r["id"] == cr_id for r in requests)

    detail_resp = client.get(f"/api/v1/admin/cancellation-requests/{cr_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["id"] == cr_id
    assert detail_resp.json()["order_id"] == order.id


def test_06_kitchen_owner_gets_403_on_admin_cancellation_routes(client: TestClient, db_session: Session):
    """6. Kitchen Owner receives HTTP 403 on admin cancellation endpoints."""
    ko_user, kitchen = _create_kitchen(db_session, "ko_06")
    cust, _ = _create_customer_with_address(db_session, "cust_06")
    biryani, _, _, _ = _setup_recipe(db_session, kitchen.id)
    order = _create_test_order(db_session, cust.id, kitchen.id, biryani, status=OrderStatus.READY)

    _login(client, cust)
    req_resp = client.post(
        f"/api/v1/customer/orders/{order.id}/cancellation-request",
        json={"reason": "Changed my mind"},
    )
    cr_id = req_resp.json()["id"]

    # Kitchen Owner attempts admin list & approve
    _login(client, ko_user)
    get_resp = client.get("/api/v1/admin/cancellation-requests")
    assert get_resp.status_code == 403

    post_resp = client.post(
        f"/api/v1/admin/cancellation-requests/{cr_id}/approve",
        json={"admin_note": "Unauthorized KO approval"},
    )
    assert post_resp.status_code == 403


def test_07_customer_cannot_access_admin_cancellation_endpoint(client: TestClient, db_session: Session):
    """7. Customer cannot access admin endpoints (HTTP 403)."""
    _, kitchen = _create_kitchen(db_session, "ko_07")
    cust, _ = _create_customer_with_address(db_session, "cust_07")
    biryani, _, _, _ = _setup_recipe(db_session, kitchen.id)
    order = _create_test_order(db_session, cust.id, kitchen.id, biryani, status=OrderStatus.READY)

    _login(client, cust)
    req_resp = client.post(
        f"/api/v1/customer/orders/{order.id}/cancellation-request",
        json={"reason": "Changed my mind"},
    )
    cr_id = req_resp.json()["id"]

    # Customer tries to access admin endpoint
    resp = client.get("/api/v1/admin/cancellation-requests")
    assert resp.status_code == 403

    decide_resp = client.post(
        f"/api/v1/admin/cancellation-requests/{cr_id}/approve",
        json={"admin_note": "Self approval"},
    )
    assert decide_resp.status_code == 403


# ── Tests 8, 9, 10, 11, 12, 13: Admin Approval, Wastage & Ledger ─────────────

def test_08_to_13_admin_approval_wastage_and_idempotency(client: TestClient, db_session: Session):
    """
    Tests 8-13:
     8. Admin approve succeeds
     9. Order becomes CANCELLED
    10. Request becomes APPROVED
    11. Wastage uses actual recipe (2 portions x 0.20 kg rice = 0.40 kg, 2 x 0.18 = 0.36 kg chicken, 2 x 0.02 = 0.04 L oil)
    12. WASTE inventory ledger created
    13. Duplicate approval cannot duplicate wastage
    """
    admin = _create_user(db_session, "admin_08", UserRole.ADMIN)
    _, kitchen = _create_kitchen(db_session, "ko_08")
    cust, _ = _create_customer_with_address(db_session, "cust_08")
    biryani, rice, chicken, oil = _setup_recipe(db_session, kitchen.id)
    order = _create_test_order(db_session, cust.id, kitchen.id, biryani, quantity=2, status=OrderStatus.READY)

    # Customer submits cancellation request
    _login(client, cust)
    cr_resp = client.post(
        f"/api/v1/customer/orders/{order.id}/cancellation-request",
        json={"reason": "Changed my mind", "customer_note": "Emergency arose"},
    )
    assert cr_resp.status_code == 200
    cr_id = cr_resp.json()["id"]

    # 8. Admin approves
    _login(client, admin)
    approve_resp = client.post(
        f"/api/v1/admin/cancellation-requests/{cr_id}/approve",
        json={"admin_note": "Approved by supervisor"},
    )
    assert approve_resp.status_code == 200
    app_data = approve_resp.json()
    assert app_data["decision"] == "APPROVED"
    assert app_data["order_status"] == "CANCELLED"

    # 9. Order becomes CANCELLED in DB
    db_session.refresh(order)
    assert order.status == OrderStatus.CANCELLED
    assert order.cancellation_reason == "Approved by supervisor"

    # 10. Request becomes APPROVED in DB
    cr = db_session.query(CancellationRequest).filter(CancellationRequest.id == cr_id).first()
    assert cr.status == "APPROVED"
    assert cr.admin_id == admin.id
    assert cr.resolved_at is not None

    # 11. Wastage uses actual recipe:
    # 2 x 0.20 kg rice = 0.40 kg
    # 2 x 0.18 kg chicken = 0.36 kg
    # 2 x 0.02 L oil = 0.04 L
    waste_records = db_session.query(WasteRecord).filter(WasteRecord.order_id == order.id).all()
    assert len(waste_records) >= 3

    waste_by_ing = {w.ingredient_id: w for w in waste_records if w.ingredient_id}
    assert rice.id in waste_by_ing
    assert chicken.id in waste_by_ing
    assert oil.id in waste_by_ing

    assert round(float(waste_by_ing[rice.id].quantity), 2) == 0.40
    assert round(float(waste_by_ing[chicken.id].quantity), 2) == 0.36
    assert round(float(waste_by_ing[oil.id].quantity), 2) == 0.04
    assert waste_by_ing[rice.id].reason == "Customer Cancellation — Admin Approved"

    # 12. WASTE inventory ledger created
    waste_txns = db_session.query(InventoryTransaction).filter(
        InventoryTransaction.reference_order_id == order.id,
        InventoryTransaction.transaction_type == InventoryTransactionType.WASTE,
    ).all()
    assert len(waste_txns) >= 3

    # 13. Duplicate approval cannot duplicate wastage (rejected with HTTP 400)
    dup_resp = client.post(
        f"/api/v1/admin/cancellation-requests/{cr_id}/approve",
        json={"admin_note": "Duplicate approval attempt"},
    )
    assert dup_resp.status_code == 400
    assert "already" in dup_resp.json()["detail"].lower()

    # Verify WasteRecords count remains 3 (no duplicate wastage)
    waste_count_after = db_session.query(WasteRecord).filter(WasteRecord.order_id == order.id).count()
    assert waste_count_after == len(waste_records)


# ── Tests 14, 15, 16, 17: Admin Rejection ────────────────────────────────────

def test_14_to_17_admin_rejection_no_wastage(client: TestClient, db_session: Session):
    """
    Tests 14-17:
    14. Admin reject succeeds (with required note)
    15. Order remains READY after rejection
    16. Rejection creates no wastage
    17. Rejection creates no WASTE ledger
    """
    admin = _create_user(db_session, "admin_14", UserRole.ADMIN)
    _, kitchen = _create_kitchen(db_session, "ko_14")
    cust, _ = _create_customer_with_address(db_session, "cust_14")
    biryani, _, _, _ = _setup_recipe(db_session, kitchen.id)
    order = _create_test_order(db_session, cust.id, kitchen.id, biryani, quantity=1, status=OrderStatus.READY)

    # Customer submits request
    _login(client, cust)
    cr_resp = client.post(
        f"/api/v1/customer/orders/{order.id}/cancellation-request",
        json={"reason": "Changed my mind"},
    )
    cr_id = cr_resp.json()["id"]

    # 14a. Rejection without reason fails
    _login(client, admin)
    bad_reject = client.post(
        f"/api/v1/admin/cancellation-requests/{cr_id}/reject",
        json={"admin_note": ""},
    )
    assert bad_reject.status_code == 400
    assert "required" in bad_reject.json()["detail"].lower()

    # 14b. Rejection with reason succeeds
    reject_resp = client.post(
        f"/api/v1/admin/cancellation-requests/{cr_id}/reject",
        json={"admin_note": "Food is already boxed and delivery partner has arrived"},
    )
    assert reject_resp.status_code == 200
    assert reject_resp.json()["decision"] == "REJECTED"

    # 15. Order remains READY
    db_session.refresh(order)
    assert order.status == OrderStatus.READY

    # Cancellation request status is REJECTED
    cr = db_session.query(CancellationRequest).filter(CancellationRequest.id == cr_id).first()
    assert cr.status == "REJECTED"
    assert cr.admin_note == "Food is already boxed and delivery partner has arrived"

    # 16. Rejection creates no wastage
    waste_count = db_session.query(WasteRecord).filter(WasteRecord.order_id == order.id).count()
    assert waste_count == 0

    # 17. Rejection creates no WASTE ledger
    waste_txns = db_session.query(InventoryTransaction).filter(
        InventoryTransaction.reference_order_id == order.id,
        InventoryTransaction.transaction_type == InventoryTransactionType.WASTE,
    ).count()
    assert waste_txns == 0


# ── Tests 18 & 19: Notifications ─────────────────────────────────────────────

def test_18_customer_receives_approval_notification(client: TestClient, db_session: Session):
    """18. Customer receives approval notification when admin approves."""
    admin = _create_user(db_session, "admin_18", UserRole.ADMIN)
    _, kitchen = _create_kitchen(db_session, "ko_18")
    cust, _ = _create_customer_with_address(db_session, "cust_18")
    biryani, _, _, _ = _setup_recipe(db_session, kitchen.id)
    order = _create_test_order(db_session, cust.id, kitchen.id, biryani, status=OrderStatus.READY)

    _login(client, cust)
    cr_id = client.post(
        f"/api/v1/customer/orders/{order.id}/cancellation-request",
        json={"reason": "Cannot receive the order"},
    ).json()["id"]

    _login(client, admin)
    client.post(
        f"/api/v1/admin/cancellation-requests/{cr_id}/approve",
        json={"admin_note": "Approved"},
    )

    # Verify notification in DB
    notif = db_session.query(Notification).filter(
        Notification.user_id == cust.id,
        Notification.event_type == "ORDER_CANCELLED",
    ).first()
    assert notif is not None
    assert "approved" in notif.message.lower()


def test_19_customer_receives_rejection_notification(client: TestClient, db_session: Session):
    """19. Customer receives rejection notification containing admin rejection reason."""
    admin = _create_user(db_session, "admin_19", UserRole.ADMIN)
    _, kitchen = _create_kitchen(db_session, "ko_19")
    cust, _ = _create_customer_with_address(db_session, "cust_19")
    biryani, _, _, _ = _setup_recipe(db_session, kitchen.id)
    order = _create_test_order(db_session, cust.id, kitchen.id, biryani, status=OrderStatus.READY)

    _login(client, cust)
    cr_id = client.post(
        f"/api/v1/customer/orders/{order.id}/cancellation-request",
        json={"reason": "Ordered by mistake"},
    ).json()["id"]

    _login(client, admin)
    rejection_reason = "Order cannot be cancelled: rider has already arrived for pickup"
    client.post(
        f"/api/v1/admin/cancellation-requests/{cr_id}/reject",
        json={"admin_note": rejection_reason},
    )

    notif = db_session.query(Notification).filter(
        Notification.user_id == cust.id,
        Notification.event_type == "CANCELLATION_REJECTED",
    ).first()
    assert notif is not None
    assert rejection_reason in notif.message


# ── Tests 20, 21, 22: Non-READY order cancellation requests rejected ─────────

def test_20_out_for_delivery_request_rejected(client: TestClient, db_session: Session):
    """20. OUT_FOR_DELIVERY request rejected with HTTP 400."""
    _, kitchen = _create_kitchen(db_session, "ko_20")
    cust, _ = _create_customer_with_address(db_session, "cust_20")
    biryani, _, _, _ = _setup_recipe(db_session, kitchen.id)
    order = _create_test_order(db_session, cust.id, kitchen.id, biryani, status=OrderStatus.OUT_FOR_DELIVERY)

    _login(client, cust)
    resp = client.post(
        f"/api/v1/customer/orders/{order.id}/cancellation-request",
        json={"reason": "Cannot receive"},
    )
    assert resp.status_code == 400
    assert "only be submitted for ready orders" in resp.json()["detail"].lower()


def test_21_delivered_request_rejected(client: TestClient, db_session: Session):
    """21. DELIVERED request rejected with HTTP 400."""
    _, kitchen = _create_kitchen(db_session, "ko_21")
    cust, _ = _create_customer_with_address(db_session, "cust_21")
    biryani, _, _, _ = _setup_recipe(db_session, kitchen.id)
    order = _create_test_order(db_session, cust.id, kitchen.id, biryani, status=OrderStatus.DELIVERED)

    _login(client, cust)
    resp = client.post(
        f"/api/v1/customer/orders/{order.id}/cancellation-request",
        json={"reason": "Cannot receive"},
    )
    assert resp.status_code == 400
    assert "only be submitted for ready orders" in resp.json()["detail"].lower()


def test_22_cancelled_request_rejected(client: TestClient, db_session: Session):
    """22. CANCELLED request rejected with HTTP 400."""
    _, kitchen = _create_kitchen(db_session, "ko_22")
    cust, _ = _create_customer_with_address(db_session, "cust_22")
    biryani, _, _, _ = _setup_recipe(db_session, kitchen.id)
    order = _create_test_order(db_session, cust.id, kitchen.id, biryani, status=OrderStatus.CANCELLED)

    _login(client, cust)
    resp = client.post(
        f"/api/v1/customer/orders/{order.id}/cancellation-request",
        json={"reason": "Cannot receive"},
    )
    assert resp.status_code == 400
    assert "only be submitted for ready orders" in resp.json()["detail"].lower()


# ── Tests 23 & 24: Repeated decisions safely rejected / idempotent ───────────

def test_23_repeated_approval_safely_rejected(client: TestClient, db_session: Session):
    """23. Repeated approval safely rejected with HTTP 400."""
    admin = _create_user(db_session, "admin_23", UserRole.ADMIN)
    _, kitchen = _create_kitchen(db_session, "ko_23")
    cust, _ = _create_customer_with_address(db_session, "cust_23")
    biryani, _, _, _ = _setup_recipe(db_session, kitchen.id)
    order = _create_test_order(db_session, cust.id, kitchen.id, biryani, status=OrderStatus.READY)

    _login(client, cust)
    cr_id = client.post(
        f"/api/v1/customer/orders/{order.id}/cancellation-request",
        json={"reason": "Changed my mind"},
    ).json()["id"]

    _login(client, admin)
    r1 = client.post(f"/api/v1/admin/cancellation-requests/{cr_id}/approve", json={"admin_note": "First approval"})
    assert r1.status_code == 200

    r2 = client.post(f"/api/v1/admin/cancellation-requests/{cr_id}/approve", json={"admin_note": "Second approval"})
    assert r2.status_code == 400
    assert "already" in r2.json()["detail"].lower()


def test_24_repeated_rejection_safely_rejected(client: TestClient, db_session: Session):
    """24. Repeated rejection safely rejected with HTTP 400."""
    admin = _create_user(db_session, "admin_24", UserRole.ADMIN)
    _, kitchen = _create_kitchen(db_session, "ko_24")
    cust, _ = _create_customer_with_address(db_session, "cust_24")
    biryani, _, _, _ = _setup_recipe(db_session, kitchen.id)
    order = _create_test_order(db_session, cust.id, kitchen.id, biryani, status=OrderStatus.READY)

    _login(client, cust)
    cr_id = client.post(
        f"/api/v1/customer/orders/{order.id}/cancellation-request",
        json={"reason": "Changed my mind"},
    ).json()["id"]

    _login(client, admin)
    r1 = client.post(f"/api/v1/admin/cancellation-requests/{cr_id}/reject", json={"admin_note": "First rejection"})
    assert r1.status_code == 200

    r2 = client.post(f"/api/v1/admin/cancellation-requests/{cr_id}/reject", json={"admin_note": "Second rejection"})
    assert r2.status_code == 400
    assert "already" in r2.json()["detail"].lower()
