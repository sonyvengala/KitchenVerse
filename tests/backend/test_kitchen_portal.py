"""
Phase 4 — Kitchen Owner Portal Tests.
Tests:
  - Kitchen owner RBAC protection
  - Dashboard stats (live DB data)
  - Order queue (scoped to kitchen)
  - Accept order + inventory consumption
  - Reject order
  - Invalid state transitions blocked
  - Valid state transitions (PREPARING, READY)
  - Menu item CRUD
  - Recipe ingredient linking
  - Ingredient CRUD
  - Inventory restock + ledger
  - Low-stock detection
  - Restocking recommendations
  - Waste records
  - Kitchen notifications
  - Cross-kitchen isolation (kitchen owner cannot see other kitchen's data)
"""

import pytest

from fastapi.testclient import TestClient

from sqlalchemy.orm import Session
from backend.app.core.security import get_password_hash
from backend.app.models.enums import UserRole, OrderStatus, PaymentStatus
from backend.app.models.user import User, KitchenProfile, CustomerProfile
from backend.app.models.menu import MenuItem, Ingredient, MenuItemIngredient
from backend.app.models.inventory import Inventory, InventoryTransaction
from backend.app.models.order import Order, OrderItem
from backend.app.models.platform import Notification


# ── Fixtures ───────────────────────────────────────────────────────────────────
def _create_user(db: Session, email: str, full_name: str, role: UserRole) -> User:
    user = User(
        email=email,
        hashed_password=get_password_hash("TestPass123!"),
        full_name=full_name,
        role=role,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.flush()
    return user


def _create_kitchen_profile(db: Session, user: User, kitchen_name: str = "Test Kitchen") -> KitchenProfile:
    profile = KitchenProfile(
        user_id=user.id,
        kitchen_name=kitchen_name,
        address="123 Kitchen Street",
        city="Mumbai",
        is_open=True,
        is_approved=True,
        rating=4.5,
        rating_count=10,
    )
    db.add(profile)
    db.flush()
    return profile


def _create_customer_profile(db: Session, user: User) -> CustomerProfile:
    profile = CustomerProfile(user_id=user.id)
    db.add(profile)
    db.flush()
    return profile


def _login_kitchen_owner(client: TestClient, email: str) -> None:
    client.post("/api/v1/auth/login", json={"email": email, "password": "TestPass123!"})


def _create_order(
    db: Session,
    customer_id: str,
    kitchen_id: str,
    order_status: OrderStatus = OrderStatus.ORDER_PLACED,
) -> Order:
    import random
    order = Order(
        order_number=f"ORD-{random.randint(100000, 999999)}",
        customer_id=customer_id,
        kitchen_id=kitchen_id,
        status=order_status,
        subtotal=250.0,
        tax=25.0,
        delivery_fee=30.0,
        total_amount=305.0,
        payment_status=PaymentStatus.PENDING,
    )
    db.add(order)
    db.flush()
    return order


# ── 1. RBAC: Customer cannot access kitchen routes ────────────────────────────
def test_customer_cannot_access_kitchen_dashboard(client: TestClient, db_session: Session):
    # Register and login as customer
    client.post("/api/v1/auth/register", json={
        "email": "cust4rbac@test.com", "password": "TestPass123!", "full_name": "RBAC Customer"
    })
    resp = client.get("/api/v1/kitchen/dashboard")
    assert resp.status_code == 403


# ── 2. Unauthenticated access blocked ────────────────────────────────────────
def test_unauthenticated_cannot_access_kitchen_routes(client: TestClient):
    # No login before this request
    fresh_client_response = client.get("/api/v1/kitchen/dashboard")
    # Should be 401 or 403
    assert fresh_client_response.status_code in [401, 403]


# ── 3. Kitchen owner can access dashboard ─────────────────────────────────────
def test_kitchen_owner_dashboard_returns_real_data(client: TestClient, db_session: Session):
    # Create kitchen owner
    owner = _create_user(db_session, "owner.dash@test.com", "Kitchen Dash Owner", UserRole.KITCHEN_OWNER)
    kitchen = _create_kitchen_profile(db_session, owner, "Dashboard Kitchen")

    # Create a customer and an order
    customer = _create_user(db_session, "cust.dash@test.com", "Dashboard Customer", UserRole.CUSTOMER)
    _create_customer_profile(db_session, customer)
    _create_order(db_session, customer.id, kitchen.id, OrderStatus.ORDER_PLACED)
    db_session.commit()

    _login_kitchen_owner(client, "owner.dash@test.com")
    resp = client.get("/api/v1/kitchen/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["kitchen_id"] == kitchen.id
    assert data["kitchen_name"] == "Dashboard Kitchen"
    assert data["pending_orders_count"] == 1
    assert data["active_orders_count"] == 0
    assert data["completed_orders_today"] == 0
    assert isinstance(data["revenue_today"], float)
    assert isinstance(data["low_stock_count"], int)


# ── 4. Order queue scoped to kitchen ─────────────────────────────────────────
def test_order_queue_scoped_to_kitchen(client: TestClient, db_session: Session):
    owner = _create_user(db_session, "owner.queue@test.com", "Queue Owner", UserRole.KITCHEN_OWNER)
    kitchen = _create_kitchen_profile(db_session, owner, "Queue Kitchen")

    # Another kitchen that should NOT be visible
    owner2 = _create_user(db_session, "owner2.queue@test.com", "Queue Owner2", UserRole.KITCHEN_OWNER)
    kitchen2 = _create_kitchen_profile(db_session, owner2, "Other Queue Kitchen")

    customer = _create_user(db_session, "cust.queue@test.com", "Queue Customer", UserRole.CUSTOMER)
    _create_customer_profile(db_session, customer)

    order_own = _create_order(db_session, customer.id, kitchen.id, OrderStatus.ORDER_PLACED)
    order_other = _create_order(db_session, customer.id, kitchen2.id, OrderStatus.ORDER_PLACED)
    db_session.commit()

    _login_kitchen_owner(client, "owner.queue@test.com")
    resp = client.get("/api/v1/kitchen/orders")
    assert resp.status_code == 200
    orders = resp.json()
    order_ids = [o["id"] for o in orders]
    assert order_own.id in order_ids
    assert order_other.id not in order_ids


# ── 5. Accept order transitions status and consumes inventory ─────────────────
def test_accept_order_with_inventory_consumption(client: TestClient, db_session: Session):
    owner = _create_user(db_session, "owner.accept@test.com", "Accept Owner", UserRole.KITCHEN_OWNER)
    kitchen = _create_kitchen_profile(db_session, owner, "Accept Kitchen")

    customer = _create_user(db_session, "cust.accept@test.com", "Accept Customer", UserRole.CUSTOMER)
    _create_customer_profile(db_session, customer)

    # Create ingredient with stock
    ingredient = Ingredient(
        kitchen_id=kitchen.id, name="Rice", unit="g",
        current_stock=500.0, minimum_stock_threshold=50.0, reorder_quantity=200.0,
    )
    db_session.add(ingredient)
    db_session.flush()

    # Create inventory record
    inv = Inventory(
        kitchen_id=kitchen.id, ingredient_id=ingredient.id,
        quantity=500.0, unit="g",
    )
    db_session.add(inv)

    # Create menu item with recipe
    menu_item = MenuItem(
        kitchen_id=kitchen.id, name="Rice Bowl", category="Rice Bowl",
        cuisine="Indian", price=150.0, is_available=True,
    )
    db_session.add(menu_item)
    db_session.flush()

    link = MenuItemIngredient(
        menu_item_id=menu_item.id, ingredient_id=ingredient.id, quantity_required=200.0
    )
    db_session.add(link)

    order = _create_order(db_session, customer.id, kitchen.id, OrderStatus.ORDER_PLACED)
    order_item = OrderItem(
        order_id=order.id, menu_item_id=menu_item.id,
        item_name="Rice Bowl", unit_price=150.0, quantity=1, subtotal=150.0,
    )
    db_session.add(order_item)
    db_session.commit()

    _login_kitchen_owner(client, "owner.accept@test.com")
    resp = client.post(f"/api/v1/kitchen/orders/{order.id}/accept")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "KITCHEN_ACCEPTED"

    # Verify inventory was consumed
    db_session.refresh(ingredient)
    # 200g consumed from 500g => 300g remaining
    assert float(ingredient.current_stock) == pytest.approx(300.0)

    # Verify transaction logged
    txn = db_session.query(InventoryTransaction).filter(
        InventoryTransaction.kitchen_id == kitchen.id,
        InventoryTransaction.ingredient_id == ingredient.id,
    ).first()
    assert txn is not None
    assert float(txn.quantity) == pytest.approx(-200.0)  # Negative = outward

    # Verify customer notification created
    notif = db_session.query(Notification).filter(
        Notification.user_id == customer.id
    ).first()
    assert notif is not None
    assert "Accepted" in notif.title or "accepted" in notif.message.lower()


# ── 6. Reject order ───────────────────────────────────────────────────────────
def test_reject_order(client: TestClient, db_session: Session):
    owner = _create_user(db_session, "owner.reject@test.com", "Reject Owner", UserRole.KITCHEN_OWNER)
    kitchen = _create_kitchen_profile(db_session, owner, "Reject Kitchen")
    customer = _create_user(db_session, "cust.reject@test.com", "Reject Cust", UserRole.CUSTOMER)
    _create_customer_profile(db_session, customer)
    order = _create_order(db_session, customer.id, kitchen.id, OrderStatus.ORDER_PLACED)
    db_session.commit()

    _login_kitchen_owner(client, "owner.reject@test.com")
    resp = client.post(f"/api/v1/kitchen/orders/{order.id}/reject", json={"rejection_reason": "Out of stock today"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "REJECTED"
    assert "out of stock" in data["rejection_reason"].lower()


# ── 7. Invalid state transition blocked ──────────────────────────────────────
def test_invalid_state_transition_blocked(client: TestClient, db_session: Session):
    owner = _create_user(db_session, "owner.invalid@test.com", "Invalid Owner", UserRole.KITCHEN_OWNER)
    kitchen = _create_kitchen_profile(db_session, owner, "Invalid Trans Kitchen")
    customer = _create_user(db_session, "cust.invalid@test.com", "Invalid Cust", UserRole.CUSTOMER)
    _create_customer_profile(db_session, customer)
    # Start at ORDER_PLACED, try to jump directly to READY (invalid)
    order = _create_order(db_session, customer.id, kitchen.id, OrderStatus.ORDER_PLACED)
    db_session.commit()

    _login_kitchen_owner(client, "owner.invalid@test.com")
    resp = client.post(f"/api/v1/kitchen/orders/{order.id}/transition", json={"target_status": "READY"})
    assert resp.status_code == 422


# ── 8. Valid transitions: KITCHEN_ACCEPTED -> PREPARING -> READY ──────────────
def test_valid_order_transitions(client: TestClient, db_session: Session):
    owner = _create_user(db_session, "owner.trans@test.com", "Trans Owner", UserRole.KITCHEN_OWNER)
    kitchen = _create_kitchen_profile(db_session, owner, "Trans Kitchen")
    customer = _create_user(db_session, "cust.trans@test.com", "Trans Cust", UserRole.CUSTOMER)
    _create_customer_profile(db_session, customer)
    order = _create_order(db_session, customer.id, kitchen.id, OrderStatus.KITCHEN_ACCEPTED)
    db_session.commit()

    _login_kitchen_owner(client, "owner.trans@test.com")

    # KITCHEN_ACCEPTED -> PREPARING
    resp = client.post(f"/api/v1/kitchen/orders/{order.id}/transition", json={"target_status": "PREPARING"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "PREPARING"

    # PREPARING -> READY
    resp = client.post(f"/api/v1/kitchen/orders/{order.id}/transition", json={"target_status": "READY"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "READY"


# ── 9. Menu item CRUD ────────────────────────────────────────────────────────
def test_menu_item_crud(client: TestClient, db_session: Session):
    owner = _create_user(db_session, "owner.menu@test.com", "Menu Owner", UserRole.KITCHEN_OWNER)
    _create_kitchen_profile(db_session, owner, "Menu Kitchen")
    db_session.commit()

    _login_kitchen_owner(client, "owner.menu@test.com")

    # Create
    resp = client.post("/api/v1/kitchen/menu", json={
        "name": "Butter Chicken", "category": "Main Course", "cuisine": "Indian",
        "price": 220.0, "is_veg": False, "is_available": True,
    })
    assert resp.status_code == 201
    item_id = resp.json()["id"]
    assert resp.json()["name"] == "Butter Chicken"

    # List
    resp = client.get("/api/v1/kitchen/menu")
    assert resp.status_code == 200
    names = [i["name"] for i in resp.json()]
    assert "Butter Chicken" in names

    # Update
    resp = client.put(f"/api/v1/kitchen/menu/{item_id}", json={"price": 250.0, "is_available": False})
    assert resp.status_code == 200
    assert resp.json()["price"] == 250.0
    assert resp.json()["is_available"] is False

    # Delete
    resp = client.delete(f"/api/v1/kitchen/menu/{item_id}")
    assert resp.status_code == 204


# ── 10. Ingredient CRUD ──────────────────────────────────────────────────────
def test_ingredient_crud(client: TestClient, db_session: Session):
    owner = _create_user(db_session, "owner.ingr@test.com", "Ingredient Owner", UserRole.KITCHEN_OWNER)
    _create_kitchen_profile(db_session, owner, "Ingredient Kitchen")
    db_session.commit()

    _login_kitchen_owner(client, "owner.ingr@test.com")

    # Create
    resp = client.post("/api/v1/kitchen/ingredients", json={
        "name": "Tomatoes", "unit": "kg", "initial_stock": 5.0,
        "minimum_stock_threshold": 1.0, "reorder_quantity": 10.0,
    })
    assert resp.status_code == 201
    ingr_id = resp.json()["id"]
    assert resp.json()["name"] == "Tomatoes"
    assert resp.json()["current_stock"] == 5.0

    # Duplicate name rejected
    resp = client.post("/api/v1/kitchen/ingredients", json={
        "name": "Tomatoes", "unit": "kg", "initial_stock": 3.0,
        "minimum_stock_threshold": 1.0, "reorder_quantity": 5.0,
    })
    assert resp.status_code == 400

    # Update threshold
    resp = client.put(f"/api/v1/kitchen/ingredients/{ingr_id}", json={"minimum_stock_threshold": 2.0})
    assert resp.status_code == 200
    assert resp.json()["minimum_stock_threshold"] == 2.0

    # List
    resp = client.get("/api/v1/kitchen/ingredients")
    assert resp.status_code == 200
    assert any(i["name"] == "Tomatoes" for i in resp.json())


# ── 11. Inventory restock + ledger ───────────────────────────────────────────
def test_restock_and_ledger(client: TestClient, db_session: Session):
    owner = _create_user(db_session, "owner.restock@test.com", "Restock Owner", UserRole.KITCHEN_OWNER)
    kitchen = _create_kitchen_profile(db_session, owner, "Restock Kitchen")
    ingredient = Ingredient(
        kitchen_id=kitchen.id, name="Oil", unit="l",
        current_stock=2.0, minimum_stock_threshold=1.0, reorder_quantity=5.0,
    )
    db_session.add(ingredient)
    db_session.flush()
    inv = Inventory(kitchen_id=kitchen.id, ingredient_id=ingredient.id, quantity=2.0, unit="l")
    db_session.add(inv)
    db_session.commit()

    _login_kitchen_owner(client, "owner.restock@test.com")

    resp = client.post("/api/v1/kitchen/inventory/restock", json={
        "ingredient_id": ingredient.id, "quantity": 8.0,
        "supplier_name": "Oil Trader", "unit_cost": 150.0,
    })
    assert resp.status_code == 200
    assert resp.json()["current_stock"] == pytest.approx(10.0)

    # Check ledger
    resp = client.get("/api/v1/kitchen/inventory/transactions")
    assert resp.status_code == 200
    txns = resp.json()
    inward = [t for t in txns if t["transaction_type"] == "INWARD"]
    assert len(inward) >= 1


# ── 12. Low-stock detection and recommendations ───────────────────────────────
def test_low_stock_detection(client: TestClient, db_session: Session):
    owner = _create_user(db_session, "owner.lowstk@test.com", "LowStock Owner", UserRole.KITCHEN_OWNER)
    kitchen = _create_kitchen_profile(db_session, owner, "LowStock Kitchen")

    # Below threshold
    ing_low = Ingredient(
        kitchen_id=kitchen.id, name="Paneer", unit="g",
        current_stock=50.0, minimum_stock_threshold=100.0, reorder_quantity=500.0,
    )
    # Above threshold
    ing_ok = Ingredient(
        kitchen_id=kitchen.id, name="Flour", unit="kg",
        current_stock=5.0, minimum_stock_threshold=1.0, reorder_quantity=10.0,
    )
    db_session.add_all([ing_low, ing_ok])
    db_session.commit()

    _login_kitchen_owner(client, "owner.lowstk@test.com")
    resp = client.get("/api/v1/kitchen/inventory/recommendations")
    assert resp.status_code == 200
    recs = resp.json()
    names = [r["ingredient_name"] for r in recs]
    assert "Paneer" in names
    assert "Flour" not in names

    # Also verify dashboard shows correct low_stock_count
    resp = client.get("/api/v1/kitchen/dashboard")
    assert resp.json()["low_stock_count"] >= 1


# ── 13. Waste records ────────────────────────────────────────────────────────
def test_waste_record(client: TestClient, db_session: Session):
    owner = _create_user(db_session, "owner.waste@test.com", "Waste Owner", UserRole.KITCHEN_OWNER)
    kitchen = _create_kitchen_profile(db_session, owner, "Waste Kitchen")
    ingredient = Ingredient(
        kitchen_id=kitchen.id, name="Onion", unit="kg",
        current_stock=10.0, minimum_stock_threshold=1.0, reorder_quantity=5.0,
    )
    db_session.add(ingredient)
    db_session.flush()
    inv = Inventory(kitchen_id=kitchen.id, ingredient_id=ingredient.id, quantity=10.0, unit="kg")
    db_session.add(inv)
    db_session.commit()

    _login_kitchen_owner(client, "owner.waste@test.com")

    resp = client.post("/api/v1/kitchen/waste", json={
        "ingredient_id": ingredient.id, "quantity": 2.0, "reason": "Spoilage due to long storage",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["quantity"] == 2.0
    assert data["reason"] == "Spoilage due to long storage"

    # Stock should have decreased
    db_session.refresh(ingredient)
    assert float(ingredient.current_stock) == pytest.approx(8.0)

    # Waste list
    resp = client.get("/api/v1/kitchen/waste")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


# ── 14. Recipe linking ───────────────────────────────────────────────────────
def test_recipe_ingredient_linking(client: TestClient, db_session: Session):
    owner = _create_user(db_session, "owner.recipe@test.com", "Recipe Owner", UserRole.KITCHEN_OWNER)
    kitchen = _create_kitchen_profile(db_session, owner, "Recipe Kitchen")
    ingredient = Ingredient(
        kitchen_id=kitchen.id, name="Milk", unit="ml",
        current_stock=2000.0, minimum_stock_threshold=200.0, reorder_quantity=1000.0,
    )
    db_session.add(ingredient)
    db_session.commit()

    _login_kitchen_owner(client, "owner.recipe@test.com")

    # Create menu item
    resp = client.post("/api/v1/kitchen/menu", json={
        "name": "Kheer", "category": "Desserts", "cuisine": "Indian",
        "price": 80.0, "is_veg": True,
    })
    assert resp.status_code == 201
    item_id = resp.json()["id"]

    # Link ingredient
    resp = client.post(f"/api/v1/kitchen/menu/{item_id}/recipe", json={
        "ingredient_id": ingredient.id, "quantity_required": 250.0,
    })
    assert resp.status_code == 201
    assert resp.json()["ingredient_id"] == ingredient.id

    # Menu item should list recipe ingredients
    resp = client.get("/api/v1/kitchen/menu")
    item_data = next(i for i in resp.json() if i["id"] == item_id)
    assert len(item_data["recipe_ingredients"]) == 1
    assert item_data["recipe_ingredients"][0]["quantity_required"] == 250.0

    # Unlink ingredient
    resp = client.delete(f"/api/v1/kitchen/menu/{item_id}/recipe/{ingredient.id}")
    assert resp.status_code == 204


# ── 15. Cross-kitchen isolation ──────────────────────────────────────────────
def test_cross_kitchen_order_isolation(client: TestClient, db_session: Session):
    owner1 = _create_user(db_session, "owner1.iso@test.com", "Kitchen Iso1", UserRole.KITCHEN_OWNER)
    kitchen1 = _create_kitchen_profile(db_session, owner1, "Isolated Kitchen 1")

    owner2 = _create_user(db_session, "owner2.iso@test.com", "Kitchen Iso2", UserRole.KITCHEN_OWNER)
    kitchen2 = _create_kitchen_profile(db_session, owner2, "Isolated Kitchen 2")

    customer = _create_user(db_session, "cust.iso@test.com", "Iso Customer", UserRole.CUSTOMER)
    _create_customer_profile(db_session, customer)

    # Order belonging to kitchen2
    order2 = _create_order(db_session, customer.id, kitchen2.id, OrderStatus.ORDER_PLACED)
    db_session.commit()

    # Login as owner1, try to access kitchen2's order
    _login_kitchen_owner(client, "owner1.iso@test.com")
    resp = client.get(f"/api/v1/kitchen/orders/{order2.id}")
    assert resp.status_code == 404


# ── 16. Delete ingredient blocked if used in recipe ──────────────────────────
def test_delete_ingredient_blocked_when_in_recipe(client: TestClient, db_session: Session):
    owner = _create_user(db_session, "owner.block@test.com", "Block Owner", UserRole.KITCHEN_OWNER)
    kitchen = _create_kitchen_profile(db_session, owner, "Block Kitchen")
    ingredient = Ingredient(
        kitchen_id=kitchen.id, name="Cream", unit="ml",
        current_stock=1000.0, minimum_stock_threshold=100.0, reorder_quantity=500.0,
    )
    db_session.add(ingredient)
    menu_item = MenuItem(
        kitchen_id=kitchen.id, name="Cream Pasta", category="Pasta", cuisine="Italian", price=200.0,
    )
    db_session.add(menu_item)
    db_session.flush()
    link = MenuItemIngredient(menu_item_id=menu_item.id, ingredient_id=ingredient.id, quantity_required=50.0)
    db_session.add(link)
    db_session.commit()

    _login_kitchen_owner(client, "owner.block@test.com")
    resp = client.delete(f"/api/v1/kitchen/ingredients/{ingredient.id}")
    assert resp.status_code == 409


# ── 17. Kitchen notifications ─────────────────────────────────────────────────
def test_kitchen_notifications(client: TestClient, db_session: Session):
    owner = _create_user(db_session, "owner.notif@test.com", "Notif Owner", UserRole.KITCHEN_OWNER)
    kitchen = _create_kitchen_profile(db_session, owner, "Notif Kitchen")

    notif = Notification(
        user_id=owner.id, title="Test Notification", message="This is a test",
        event_type="NOTIFICATION_CREATED",
    )
    db_session.add(notif)
    db_session.commit()

    _login_kitchen_owner(client, "owner.notif@test.com")
    resp = client.get("/api/v1/kitchen/notifications")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1

    notif_id = resp.json()[0]["id"]
    resp = client.put(f"/api/v1/kitchen/notifications/{notif_id}/read")
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"


# ── 18. Kitchen settings update ──────────────────────────────────────────────
def test_kitchen_settings_update(client: TestClient, db_session: Session):
    owner = _create_user(db_session, "owner.settings@test.com", "Settings Owner", UserRole.KITCHEN_OWNER)
    _create_kitchen_profile(db_session, owner, "Settings Kitchen")
    db_session.commit()

    _login_kitchen_owner(client, "owner.settings@test.com")

    resp = client.put("/api/v1/kitchen/settings", json={
        "kitchen_name": "Updated Kitchen Name", "is_open": False, "description": "Best kitchen in town"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["kitchen_name"] == "Updated Kitchen Name"
    assert data["is_open"] is False
    assert data["description"] == "Best kitchen in town"
