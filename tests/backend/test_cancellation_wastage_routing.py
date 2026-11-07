"""
Comprehensive tests for 3 Real CloudKitchen Features:
Feature 1: Customer Order Cancellation + Wastage
Feature 2: Automatic Wastage Calculation + Wastage Analytics
Feature 3: Kitchen Owner Delivery Route Map & Security

Covers all 15 test scenarios specified in requirements:
1. Customer cancels before preparation -> CANCELLED, no wastage.
2. Customer cancels during PREPARING -> CANCELLED, wastage created automatically.
3. Customer cancels after READY -> cancellation rejected according to policy.
4. Automatic wastage quantity is correctly calculated from recipe * ordered quantity.
5. Wastage does not get created twice for the same cancellation.
6. Normal order ingredient deduction is not counted as wastage.
7. Wastage inventory transaction is recorded correctly.
8. Monthly wastage totals are calculated from real records.
9. Wastage by reason / menu item / ingredient works.
10. Wastage rate calculation works (wasted / prepared * 100).
11. Kitchen Owner can see route for their own order.
12. Kitchen Owner cannot access another kitchen's customer address/route.
13. Customer's historical order address remains unchanged after editing saved addresses.
14. Missing location/routing data is handled safely without fake data.
15. Customer cancellation API enforces cancellation rules server-side.
"""

import uuid
import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.security import get_password_hash
from backend.app.models.user import User, Address, KitchenProfile
from backend.app.models.enums import UserRole, OrderStatus, InventoryTransactionType
from backend.app.models.menu import MenuItem, Ingredient, MenuItemIngredient
from backend.app.models.order import Order, OrderItem
from backend.app.models.inventory import WasteRecord, InventoryTransaction, Purchase, Inventory


# ── Test Helpers ─────────────────────────────────────────────────────────────
def _create_kitchen(db: Session, email_prefix: str, lat: float = 12.9716, lng: float = 77.5946):
    user = User(
        email=f"{email_prefix}_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=get_password_hash("ChefSecret123!"),
        full_name="Master Chef",
        role=UserRole.KITCHEN_OWNER,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()

    kitchen = KitchenProfile(
        user_id=user.id,
        kitchen_name="Biryani Express Kitchen",
        description="Authentic Dum Biryanis",
        address="100 Commercial Street, Tasker Town",
        city="Bangalore",
        state="Karnataka",
        postal_code="560001",
        phone="+919876543210",
        latitude=lat,
        longitude=lng,
        is_open=True,
        is_approved=True,
        approval_status="APPROVED",
    )
    db.add(kitchen)
    db.commit()
    return user, kitchen


def _create_customer(db: Session, email_prefix: str, lat: float = 12.9352, lng: float = 77.6245):
    user = User(
        email=f"{email_prefix}_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=get_password_hash("CustSecret123!"),
        full_name="Rahul Sharma",
        role=UserRole.CUSTOMER,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()

    address = Address(
        user_id=user.id,
        address_line1="Apartment 4B, Koramangala 4th Block",
        city="Bangalore",
        state="Karnataka",
        postal_code="560034",
        landmark="Near Sony World Signal",
        latitude=lat,
        longitude=lng,
        is_default=True,
    )
    db.add(address)
    db.commit()
    return user, address


def _setup_biryani_menu_and_recipe(db: Session, kitchen_id: str):
    # Ingredients with initial stock 10.0
    rice = Ingredient(
        kitchen_id=kitchen_id,
        name="Basmati Rice",
        unit="kg",
        current_stock=10.0,
        minimum_stock_threshold=2.0,
        reorder_quantity=20.0,
    )
    chicken = Ingredient(
        kitchen_id=kitchen_id,
        name="Fresh Chicken",
        unit="kg",
        current_stock=10.0,
        minimum_stock_threshold=2.0,
        reorder_quantity=20.0,
    )
    oil = Ingredient(
        kitchen_id=kitchen_id,
        name="Cooking Oil",
        unit="L",
        current_stock=10.0,
        minimum_stock_threshold=2.0,
        reorder_quantity=20.0,
    )
    db.add_all([rice, chicken, oil])
    db.commit()

    # Inventory records
    inv_rice = Inventory(kitchen_id=kitchen_id, ingredient_id=rice.id, quantity=10.0, unit="kg")
    inv_chicken = Inventory(kitchen_id=kitchen_id, ingredient_id=chicken.id, quantity=10.0, unit="kg")
    inv_oil = Inventory(kitchen_id=kitchen_id, ingredient_id=oil.id, quantity=10.0, unit="L")
    db.add_all([inv_rice, inv_chicken, inv_oil])

    # Purchases to establish unit costs: ₹60/kg rice, ₹200/kg chicken, ₹120/L oil
    p_rice = Purchase(kitchen_id=kitchen_id, ingredient_id=rice.id, supplier_name="Metro Cash & Carry", unit="kg", quantity=10.0, unit_cost=60.0, total_cost=600.0)
    p_chicken = Purchase(kitchen_id=kitchen_id, ingredient_id=chicken.id, supplier_name="Fresh Farm", unit="kg", quantity=10.0, unit_cost=200.0, total_cost=2000.0)
    p_oil = Purchase(kitchen_id=kitchen_id, ingredient_id=oil.id, supplier_name="Fortune Oil", unit="L", quantity=10.0, unit_cost=120.0, total_cost=1200.0)
    db.add_all([p_rice, p_chicken, p_oil])
    db.commit()

    # Menu Item
    biryani = MenuItem(
        kitchen_id=kitchen_id,
        name="Chicken Biryani",
        category="Biryani",
        cuisine="Mughlai",
        price=250.0,
        is_available=True,
        is_veg=False,
    )
    db.add(biryani)
    db.commit()

    # Recipe: Rice=0.20 kg, Chicken=0.18 kg, Oil=0.02 L
    r1 = MenuItemIngredient(menu_item_id=biryani.id, ingredient_id=rice.id, quantity_required=0.20)
    r2 = MenuItemIngredient(menu_item_id=biryani.id, ingredient_id=chicken.id, quantity_required=0.18)
    r3 = MenuItemIngredient(menu_item_id=biryani.id, ingredient_id=oil.id, quantity_required=0.02)
    db.add_all([r1, r2, r3])
    db.commit()

    return biryani, rice, chicken, oil


# ── Test Cases ───────────────────────────────────────────────────────────────

def test_scenario_1_cancel_before_preparation_no_wastage(client: TestClient, db_session: Session):
    """
    Scenario 1: Customer cancels BEFORE food preparation starts.
    -> Order becomes CANCELLED.
    -> No wastage record is created.
    -> Stock is restored.
    """
    ko_user, kitchen = _create_kitchen(db_session, "ko1")
    cust_user, address = _create_customer(db_session, "cust1")
    biryani, rice, chicken, oil = _setup_biryani_menu_and_recipe(db_session, kitchen.id)

    # Place order for 2 Biryanis
    client.post("/api/v1/auth/login", json={"email": cust_user.email, "password": "CustSecret123!"})
    resp = client.post("/api/v1/customer/orders", json={
        "kitchen_id": kitchen.id,
        "items": [{"menu_item_id": biryani.id, "quantity": 2}],
        "delivery_address_id": address.id,
    })
    assert resp.status_code == 201
    order_id = resp.json()["id"]

    # Kitchen Owner accepts order (inventory deducted)
    client.post("/api/v1/auth/login", json={"email": ko_user.email, "password": "ChefSecret123!"})
    acc_resp = client.post(f"/api/v1/kitchen/orders/{order_id}/accept")
    assert acc_resp.status_code == 200

    db_session.refresh(rice)
    assert round(float(rice.current_stock), 2) == 9.60  # 10 - 2 * 0.20

    # Customer cancels BEFORE PREPARING (order is in KITCHEN_ACCEPTED)
    client.post("/api/v1/auth/login", json={"email": cust_user.email, "password": "CustSecret123!"})
    cancel_resp = client.post(f"/api/v1/customer/orders/{order_id}/cancel?reason=Changed+mind")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "CANCELLED"

    # Verify NO wastage record was created
    waste_count = db_session.query(WasteRecord).filter(WasteRecord.order_id == order_id).count()
    assert waste_count == 0

    # Verify inventory was restored
    db_session.refresh(rice)
    assert round(float(rice.current_stock), 2) == 10.00


def test_scenario_2_and_4_cancel_during_preparing_creates_wastage(client: TestClient, db_session: Session):
    """
    Scenario 2 & 4: Customer cancels AFTER PREPARING has started.
    -> Order becomes CANCELLED.
    -> Wastage records created automatically.
    -> Quantities: Rice=2*0.20=0.40kg, Chicken=2*0.18=0.36kg, Oil=2*0.02=0.04L.
    """
    ko_user, kitchen = _create_kitchen(db_session, "ko2")
    cust_user, address = _create_customer(db_session, "cust2")
    biryani, rice, chicken, oil = _setup_biryani_menu_and_recipe(db_session, kitchen.id)

    # Customer places order for 2 Biryanis
    client.post("/api/v1/auth/login", json={"email": cust_user.email, "password": "CustSecret123!"})
    order_resp = client.post("/api/v1/customer/orders", json={
        "kitchen_id": kitchen.id,
        "items": [{"menu_item_id": biryani.id, "quantity": 2}],
        "delivery_address_id": address.id,
    })
    order_id = order_resp.json()["id"]

    # Kitchen accepts and transitions to PREPARING
    client.post("/api/v1/auth/login", json={"email": ko_user.email, "password": "ChefSecret123!"})
    client.post(f"/api/v1/kitchen/orders/{order_id}/accept")
    prep_resp = client.post(f"/api/v1/kitchen/orders/{order_id}/transition", json={"target_status": "PREPARING"})
    assert prep_resp.status_code == 200

    # Customer cancels during PREPARING
    client.post("/api/v1/auth/login", json={"email": cust_user.email, "password": "CustSecret123!"})
    cancel_resp = client.post(f"/api/v1/customer/orders/{order_id}/cancel?reason=Emergency")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "CANCELLED"

    # Verify automatic wastage records
    waste_records = db_session.query(WasteRecord).filter(WasteRecord.order_id == order_id).all()
    assert len(waste_records) == 3

    waste_by_ing = {w.ingredient_id: w for w in waste_records}
    assert round(float(waste_by_ing[rice.id].quantity), 2) == 0.40
    assert round(float(waste_by_ing[chicken.id].quantity), 2) == 0.36
    assert round(float(waste_by_ing[oil.id].quantity), 2) == 0.04

    # Verify reason and menu item info
    assert waste_by_ing[rice.id].reason == "CUSTOMER_CANCELLED_AFTER_PREPARATION"
    assert waste_by_ing[rice.id].menu_item_name == "Chicken Biryani"
    assert waste_by_ing[rice.id].portions_wasted == 2.0

    # Verify estimated cost: Rice=0.40 * 60 = 24.0, Chicken=0.36 * 200 = 72.0, Oil=0.04 * 120 = 4.8
    assert round(float(waste_by_ing[rice.id].estimated_cost), 2) == 24.0
    assert round(float(waste_by_ing[chicken.id].estimated_cost), 2) == 72.0
    assert round(float(waste_by_ing[oil.id].estimated_cost), 2) == 4.8


def test_scenario_3_cancel_after_ready_is_rejected(client: TestClient, db_session: Session):
    """
    Scenario 3: Customer tries to cancel when order is READY, OUT_FOR_DELIVERY, or DELIVERED.
    -> Cancellation rejected server-side with 400 Bad Request.
    """
    ko_user, kitchen = _create_kitchen(db_session, "ko3")
    cust_user, address = _create_customer(db_session, "cust3")
    biryani, rice, chicken, oil = _setup_biryani_menu_and_recipe(db_session, kitchen.id)

    # Customer places order
    client.post("/api/v1/auth/login", json={"email": cust_user.email, "password": "CustSecret123!"})
    resp = client.post("/api/v1/customer/orders", json={
        "kitchen_id": kitchen.id,
        "items": [{"menu_item_id": biryani.id, "quantity": 1}],
        "delivery_address_id": address.id,
    })
    order_id = resp.json()["id"]

    # Kitchen transitions to READY
    client.post("/api/v1/auth/login", json={"email": ko_user.email, "password": "ChefSecret123!"})
    client.post(f"/api/v1/kitchen/orders/{order_id}/accept")
    client.post(f"/api/v1/kitchen/orders/{order_id}/transition", json={"target_status": "PREPARING"})
    ready_resp = client.post(f"/api/v1/kitchen/orders/{order_id}/transition", json={"target_status": "READY"})
    assert ready_resp.status_code == 200

    # Customer tries to cancel when READY
    client.post("/api/v1/auth/login", json={"email": cust_user.email, "password": "CustSecret123!"})
    cancel_resp = client.post(f"/api/v1/customer/orders/{order_id}/cancel")
    assert cancel_resp.status_code == 400
    assert "ready" in cancel_resp.json()["detail"].lower()

    # Order remains READY
    order = db_session.query(Order).filter(Order.id == order_id).first()
    assert order.status == OrderStatus.READY


def test_scenario_5_prevent_duplicate_wastage_records(client: TestClient, db_session: Session):
    """
    Scenario 5: Prevent duplicate wastage records if cancellation event is re-processed.
    """
    ko_user, kitchen = _create_kitchen(db_session, "ko5")
    cust_user, address = _create_customer(db_session, "cust5")
    biryani, rice, chicken, oil = _setup_biryani_menu_and_recipe(db_session, kitchen.id)

    client.post("/api/v1/auth/login", json={"email": cust_user.email, "password": "CustSecret123!"})
    resp = client.post("/api/v1/customer/orders", json={
        "kitchen_id": kitchen.id,
        "items": [{"menu_item_id": biryani.id, "quantity": 1}],
        "delivery_address_id": address.id,
    })
    order_id = resp.json()["id"]

    client.post("/api/v1/auth/login", json={"email": ko_user.email, "password": "ChefSecret123!"})
    client.post(f"/api/v1/kitchen/orders/{order_id}/accept")
    client.post(f"/api/v1/kitchen/orders/{order_id}/transition", json={"target_status": "PREPARING"})

    # First cancel
    client.post("/api/v1/auth/login", json={"email": cust_user.email, "password": "CustSecret123!"})
    c1 = client.post(f"/api/v1/customer/orders/{order_id}/cancel")
    assert c1.status_code == 200

    initial_waste_count = db_session.query(WasteRecord).filter(WasteRecord.order_id == order_id).count()
    assert initial_waste_count == 3

    # Attempt second cancel
    c2 = client.post(f"/api/v1/customer/orders/{order_id}/cancel")
    assert c2.status_code == 400  # Already cancelled

    subsequent_waste_count = db_session.query(WasteRecord).filter(WasteRecord.order_id == order_id).count()
    assert subsequent_waste_count == initial_waste_count


def test_scenario_6_and_7_inventory_transactions_distinguish_consumption_and_waste(client: TestClient, db_session: Session):
    """
    Scenario 6 & 7: Normal order consumption vs wastage are separate inventory ledger transactions.
    Normal order creates OUTWARD_ORDER.
    Cancelled preparing order creates separate WASTE transaction.
    """
    ko_user, kitchen = _create_kitchen(db_session, "ko6")
    cust_user, address = _create_customer(db_session, "cust6")
    biryani, rice, chicken, oil = _setup_biryani_menu_and_recipe(db_session, kitchen.id)

    # Normal completed order
    client.post("/api/v1/auth/login", json={"email": cust_user.email, "password": "CustSecret123!"})
    resp1 = client.post("/api/v1/customer/orders", json={
        "kitchen_id": kitchen.id,
        "items": [{"menu_item_id": biryani.id, "quantity": 1}],
        "delivery_address_id": address.id,
    })
    ord1_id = resp1.json()["id"]

    client.post("/api/v1/auth/login", json={"email": ko_user.email, "password": "ChefSecret123!"})
    client.post(f"/api/v1/kitchen/orders/{ord1_id}/accept")
    client.post(f"/api/v1/kitchen/orders/{ord1_id}/transition", json={"target_status": "PREPARING"})
    client.post(f"/api/v1/kitchen/orders/{ord1_id}/transition", json={"target_status": "READY"})
    client.post(f"/api/v1/kitchen/orders/{ord1_id}/transition", json={"target_status": "DELIVERED"})

    # Check transactions for ord1_id: ONLY OUTWARD_ORDER, NO WASTE
    tx_ord1 = db_session.query(InventoryTransaction).filter(
        InventoryTransaction.reference_order_id == ord1_id
    ).all()
    assert all(tx.transaction_type == InventoryTransactionType.OUTWARD_ORDER for tx in tx_ord1)
    assert not any(tx.transaction_type == InventoryTransactionType.WASTE for tx in tx_ord1)

    # Cancelled prepared order
    client.post("/api/v1/auth/login", json={"email": cust_user.email, "password": "CustSecret123!"})
    resp2 = client.post("/api/v1/customer/orders", json={
        "kitchen_id": kitchen.id,
        "items": [{"menu_item_id": biryani.id, "quantity": 1}],
        "delivery_address_id": address.id,
    })
    ord2_id = resp2.json()["id"]

    client.post("/api/v1/auth/login", json={"email": ko_user.email, "password": "ChefSecret123!"})
    client.post(f"/api/v1/kitchen/orders/{ord2_id}/accept")
    client.post(f"/api/v1/kitchen/orders/{ord2_id}/transition", json={"target_status": "PREPARING"})

    client.post("/api/v1/auth/login", json={"email": cust_user.email, "password": "CustSecret123!"})
    client.post(f"/api/v1/customer/orders/{ord2_id}/cancel")

    # Check transactions for ord2_id: must have WASTE transactions
    tx_ord2 = db_session.query(InventoryTransaction).filter(
        InventoryTransaction.reference_order_id == ord2_id
    ).all()
    waste_tx = [t for t in tx_ord2 if t.transaction_type == InventoryTransactionType.WASTE]
    assert len(waste_tx) == 3


def test_scenario_8_9_10_monthly_wastage_analytics(client: TestClient, db_session: Session):
    """
    Scenario 8, 9, 10: Kitchen Owner Wastage Analytics.
    - Total Wastage Cost in ₹
    - Number of Wasted Orders
    - Total Wasted Portions
    - Wastage Rate = (wasted portions / prepared portions * 100)
    - Breakdowns by reason, menu item, ingredient.
    """
    ko_user, kitchen = _create_kitchen(db_session, "ko8")
    cust_user, address = _create_customer(db_session, "cust8")
    biryani, rice, chicken, oil = _setup_biryani_menu_and_recipe(db_session, kitchen.id)

    # 1 delivered order (2 portions prepared)
    client.post("/api/v1/auth/login", json={"email": cust_user.email, "password": "CustSecret123!"})
    r1 = client.post("/api/v1/customer/orders", json={
        "kitchen_id": kitchen.id,
        "items": [{"menu_item_id": biryani.id, "quantity": 2}],
        "delivery_address_id": address.id,
    })
    o1_id = r1.json()["id"]

    client.post("/api/v1/auth/login", json={"email": ko_user.email, "password": "ChefSecret123!"})
    client.post(f"/api/v1/kitchen/orders/{o1_id}/accept")
    client.post(f"/api/v1/kitchen/orders/{o1_id}/transition", json={"target_status": "PREPARING"})
    client.post(f"/api/v1/kitchen/orders/{o1_id}/transition", json={"target_status": "DELIVERED"})

    # 1 cancelled preparing order (1 portion wasted)
    client.post("/api/v1/auth/login", json={"email": cust_user.email, "password": "CustSecret123!"})
    r2 = client.post("/api/v1/customer/orders", json={
        "kitchen_id": kitchen.id,
        "items": [{"menu_item_id": biryani.id, "quantity": 1}],
        "delivery_address_id": address.id,
    })
    o2_id = r2.json()["id"]

    client.post("/api/v1/auth/login", json={"email": ko_user.email, "password": "ChefSecret123!"})
    client.post(f"/api/v1/kitchen/orders/{o2_id}/accept")
    client.post(f"/api/v1/kitchen/orders/{o2_id}/transition", json={"target_status": "PREPARING"})

    client.post("/api/v1/auth/login", json={"email": cust_user.email, "password": "CustSecret123!"})
    client.post(f"/api/v1/customer/orders/{o2_id}/cancel")

    # Fetch Kitchen Owner Wastage Analytics
    now = datetime.now()
    client.post("/api/v1/auth/login", json={"email": ko_user.email, "password": "ChefSecret123!"})
    an_resp = client.post if False else client.get(f"/api/v1/kitchen/waste/analytics?year={now.year}&month={now.month}")
    assert an_resp.status_code == 200
    analytics = an_resp.json()

    assert analytics["wasted_orders_count"] == 1
    assert analytics["total_wasted_portions"] == 1.0
    assert analytics["prepared_food_portions"] == 3.0  # 2 in order 1 + 1 in order 2
    # Wastage Rate = 1 / 3 * 100 = 33.33%
    assert round(analytics["wastage_rate"], 1) == 33.3

    # Total cost = 0.20*60 (12) + 0.18*200 (36) + 0.02*120 (2.4) = 50.40
    assert round(analytics["total_cost"], 2) == 50.40

    # Breakdowns
    assert any("cancelled after preparation" in r["reason"].lower() or r["reason"] == "CUSTOMER_CANCELLED_AFTER_PREPARATION" for r in analytics["by_reason"])
    assert any(m["menu_item_name"] == "Chicken Biryani" for m in analytics["by_menu_item"])
    assert any(i["ingredient_name"] == "Basmati Rice" for i in analytics["by_ingredient"])


def test_scenario_11_kitchen_owner_can_see_delivery_route_for_own_order(client: TestClient, db_session: Session):
    """
    Scenario 11: Kitchen Owner can see delivery route for their own order.
    From kitchen registered lat/lng to customer delivery address lat/lng.
    """
    ko_user, kitchen = _create_kitchen(db_session, "ko11", lat=12.9716, lng=77.5946)
    cust_user, address = _create_customer(db_session, "cust11", lat=12.9352, lng=77.6245)
    biryani, rice, chicken, oil = _setup_biryani_menu_and_recipe(db_session, kitchen.id)

    client.post("/api/v1/auth/login", json={"email": cust_user.email, "password": "CustSecret123!"})
    r = client.post("/api/v1/customer/orders", json={
        "kitchen_id": kitchen.id,
        "items": [{"menu_item_id": biryani.id, "quantity": 1}],
        "delivery_address_id": address.id,
    })
    order_id = r.json()["id"]

    # Kitchen Owner checks delivery route
    client.post("/api/v1/auth/login", json={"email": ko_user.email, "password": "ChefSecret123!"})
    route_resp = client.get(f"/api/v1/kitchen/orders/{order_id}/delivery-route")
    assert route_resp.status_code == 200
    route = route_resp.json()

    assert route["order_id"] == order_id
    assert route["kitchen"]["name"] == "Biryani Express Kitchen"
    assert round(route["kitchen"]["latitude"], 4) == 12.9716
    assert round(route["kitchen"]["longitude"], 4) == 77.5946
    assert round(route["customer"]["latitude"], 4) == 12.9352
    assert round(route["customer"]["longitude"], 4) == 77.6245
    assert "google.com/maps" in route["maps_url"] or "maps.google.com" in route["maps_url"]


def test_scenario_12_route_security_kitchen_owner_cannot_access_other_kitchen_order(client: TestClient, db_session: Session):
    """
    Scenario 12: Route Security - Kitchen Owner cannot access another kitchen's order route/customer address.
    Enforced server-side.
    """
    ko_user_1, kitchen_1 = _create_kitchen(db_session, "ko12_1")
    ko_user_2, kitchen_2 = _create_kitchen(db_session, "ko12_2")
    cust_user, address = _create_customer(db_session, "cust12")
    biryani, rice, chicken, oil = _setup_biryani_menu_and_recipe(db_session, kitchen_1.id)

    # Order belonging to Kitchen 1
    client.post("/api/v1/auth/login", json={"email": cust_user.email, "password": "CustSecret123!"})
    r = client.post("/api/v1/customer/orders", json={
        "kitchen_id": kitchen_1.id,
        "items": [{"menu_item_id": biryani.id, "quantity": 1}],
        "delivery_address_id": address.id,
    })
    k1_order_id = r.json()["id"]

    # Kitchen Owner 2 tries to access Kitchen 1's delivery route
    client.post("/api/v1/auth/login", json={"email": ko_user_2.email, "password": "ChefSecret123!"})
    forbidden_resp = client.get(f"/api/v1/kitchen/orders/{k1_order_id}/delivery-route")
    assert forbidden_resp.status_code in [403, 404]


def test_scenario_13_customer_order_address_snapshot_immutability(client: TestClient, db_session: Session):
    """
    Scenario 13: Customer edits their saved address after order placement.
    The past order's delivery address snapshot must NOT change.
    """
    ko_user, kitchen = _create_kitchen(db_session, "ko13")
    cust_user, address = _create_customer(db_session, "cust13", lat=12.9352, lng=77.6245)
    biryani, rice, chicken, oil = _setup_biryani_menu_and_recipe(db_session, kitchen.id)

    # Place order
    client.post("/api/v1/auth/login", json={"email": cust_user.email, "password": "CustSecret123!"})
    r = client.post("/api/v1/customer/orders", json={
        "kitchen_id": kitchen.id,
        "items": [{"menu_item_id": biryani.id, "quantity": 1}],
        "delivery_address_id": address.id,
    })
    order_id = r.json()["id"]

    # Customer updates saved address to new location
    update_resp = client.put(f"/api/v1/customer/addresses/{address.id}", json={
        "address_line1": "999 MG Road, Trinity Circle",
        "city": "Bangalore",
        "state": "Karnataka",
        "postal_code": "560001",
        "latitude": 12.9750,
        "longitude": 77.6100,
    })
    assert update_resp.status_code == 200

    # Verify the past order still retains original snapshot
    order = db_session.query(Order).filter(Order.id == order_id).first()
    assert "Koramangala" in order.delivery_address_text
    assert round(order.delivery_latitude, 4) == 12.9352
    assert round(order.delivery_longitude, 4) == 77.6245


def test_scenario_14_missing_location_data_handled_safely_no_fake_data(client: TestClient, db_session: Session):
    """
    Scenario 14: When kitchen or customer coordinates are missing,
    route_available is False, message clearly indicates route unavailable,
    and no fake coordinates or distances are invented.
    """
    ko_user, kitchen = _create_kitchen(db_session, "ko14", lat=None, lng=None)  # No lat/lng
    cust_user, address = _create_customer(db_session, "cust14", lat=None, lng=None)
    biryani, rice, chicken, oil = _setup_biryani_menu_and_recipe(db_session, kitchen.id)

    client.post("/api/v1/auth/login", json={"email": cust_user.email, "password": "CustSecret123!"})
    r = client.post("/api/v1/customer/orders", json={
        "kitchen_id": kitchen.id,
        "items": [{"menu_item_id": biryani.id, "quantity": 1}],
        "delivery_address_id": address.id,
    })
    order_id = r.json()["id"]

    client.post("/api/v1/auth/login", json={"email": ko_user.email, "password": "ChefSecret123!"})
    route_resp = client.get(f"/api/v1/kitchen/orders/{order_id}/delivery-route")
    assert route_resp.status_code == 200
    route = route_resp.json()

    assert route["route_available"] is False
    assert "Route unavailable" in route["message"]
    assert route["distance_km"] is None
    assert route["duration_minutes"] is None
    assert route["route_coordinates"] is None


def test_scenario_15_server_side_cancellation_rules_enforcement(client: TestClient, db_session: Session):
    """
    Scenario 15: Server-side cancellation enforcement.
    Client cannot bypass UI to cancel orders in READY, OUT_FOR_DELIVERY, or DELIVERED.
    """
    ko_user, kitchen = _create_kitchen(db_session, "ko15")
    cust_user, address = _create_customer(db_session, "cust15")
    biryani, rice, chicken, oil = _setup_biryani_menu_and_recipe(db_session, kitchen.id)

    client.post("/api/v1/auth/login", json={"email": cust_user.email, "password": "CustSecret123!"})
    r = client.post("/api/v1/customer/orders", json={
        "kitchen_id": kitchen.id,
        "items": [{"menu_item_id": biryani.id, "quantity": 1}],
        "delivery_address_id": address.id,
    })
    order_id = r.json()["id"]

    client.post("/api/v1/auth/login", json={"email": ko_user.email, "password": "ChefSecret123!"})
    client.post(f"/api/v1/kitchen/orders/{order_id}/accept")
    client.post(f"/api/v1/kitchen/orders/{order_id}/transition", json={"target_status": "PREPARING"})
    client.post(f"/api/v1/kitchen/orders/{order_id}/transition", json={"target_status": "READY"})
    client.post(f"/api/v1/kitchen/orders/{order_id}/transition", json={"target_status": "OUT_FOR_DELIVERY"})

    # Direct API cancellation attempt
    client.post("/api/v1/auth/login", json={"email": cust_user.email, "password": "CustSecret123!"})
    direct_cancel = client.post(f"/api/v1/customer/orders/{order_id}/cancel")
    assert direct_cancel.status_code == 400
    assert "cancellation is no longer available" in direct_cancel.json()["detail"].lower()
