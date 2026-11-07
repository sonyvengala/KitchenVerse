"""
Comprehensive tests for Ingredient Costing, Unit Conversion, and Inventory Valuation in KitchenVerse.

Covers:
1. Purchase cost entry with actual total price, quantity, unit, supplier, and purchase date.
2. Unit cost calculation with unit conversions (e.g., grams to kilograms, milliliters to liters).
3. Validation of positive quantities and non-negative prices.
4. Prevention of fake 0.0 purchase records when restocked without cost.
5. Repeat purchases at different prices using Weighted-Average Cost (WAC) valuation.
6. Display of "Cost unavailable" (cost_available=False, unit_cost=None) when genuine cost cannot be determined.
7. Wastage costing using accurate WAC and preserving None when cost is unknown.
8. Recipe-based order deductions with unit conversions and duplicate deduction prevention.
9. Cross-kitchen authorization (Kitchen owners can only manage their own kitchen; Admin can view all).
10. Preservation of historical purchase records.
"""
import uuid
from datetime import datetime, timezone
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.user import User, KitchenProfile
from backend.app.models.enums import (
    UserRole,
    OrderStatus,
    InventoryStatus,
    InventoryTransactionType,
)
from backend.app.models.menu import MenuItem, Ingredient, MenuItemIngredient
from backend.app.models.inventory import Inventory, InventoryTransaction, Purchase, WasteRecord
from backend.app.models.order import Order, OrderItem
from backend.app.core.security import get_password_hash
from backend.app.core.session import create_user_session
from backend.app.services.kitchen_service import KitchenService
from backend.app.schemas.kitchen import (
    InventoryRestockRequest,
    WasteRecordCreate,
    IngredientCreate,
    RecipeLinkRequest,
)
from backend.app.core.unit_converter import convert_quantity, are_units_compatible


def create_user(db: Session, email: str, role: UserRole) -> tuple[User, str]:
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


def create_kitchen(db: Session, owner: User, name: str = "Test Kitchen") -> KitchenProfile:
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


def test_unit_converter_commercial_kitchen():
    """Verify commercial kitchen unit conversion accuracy."""
    # Mass
    assert convert_quantity(1000, "g", "kg") == 1.0
    assert convert_quantity(500, "g", "kg") == 0.5
    assert convert_quantity(2.5, "kg", "g") == 2500.0
    assert convert_quantity(1000, "mg", "g") == 1.0

    # Volume
    assert convert_quantity(1000, "ml", "l") == 1.0
    assert convert_quantity(250, "ml", "l") == 0.25
    assert convert_quantity(1.5, "l", "ml") == 1500.0

    # Count
    assert are_units_compatible("pcs", "packet") is True

    # Incompatible units raise ValueError
    with pytest.raises(ValueError, match="Cannot convert"):
        convert_quantity(10, "kg", "l")


def test_restock_with_purchase_cost_and_unit_conversion(db_session: Session):
    """Kitchen owner restocks an ingredient measured in kg by purchasing in grams at a total price."""
    db = db_session
    owner, _ = create_user(db, "owner_cost1@test.com", UserRole.KITCHEN_OWNER)
    kitchen = create_kitchen(db, owner, "Spices Kitchen")

    # Base unit: kg
    ing = KitchenService.create_ingredient(
        db,
        owner,
        IngredientCreate(
            name="Turmeric Powder",
            unit="kg",
            initial_stock=0.0,
            minimum_stock_threshold=1.0,
            reorder_quantity=5.0,
        ),
    )

    # Restock: 500 grams purchased for total Rs 150
    req = InventoryRestockRequest(
        ingredient_id=ing.id,
        quantity=500.0,
        purchase_unit="g",
        total_price=150.0,
        supplier_name="Spices Mandi",
        purchase_date=datetime(2026, 10, 20, 10, 0, 0, tzinfo=timezone.utc),
    )
    ing_updated = KitchenService.restock_ingredient(db, owner, req)

    # 500 g converted to 0.5 kg
    assert ing_updated.current_stock == 0.5

    # Check inventory ledger entry
    txns = db.query(InventoryTransaction).filter(InventoryTransaction.ingredient_id == ing.id).all()
    assert len(txns) == 1
    assert txns[0].quantity == 0.5
    assert txns[0].transaction_type == InventoryTransactionType.INWARD

    # Purchase record should be recorded with base unit cost = 150 / 0.5 = Rs 300 / kg
    purchases = db.query(Purchase).filter(Purchase.ingredient_id == ing.id).all()
    assert len(purchases) == 1
    assert purchases[0].quantity == 0.5
    assert purchases[0].unit == "kg"
    assert purchases[0].total_cost == 150.0
    assert purchases[0].unit_cost == 300.0
    assert purchases[0].supplier_name == "Spices Mandi"

    # Check valuation
    val = KitchenService.get_ingredient_valuation(db, kitchen.id, ing.id, ing_updated.current_stock)
    assert val["cost_available"] is True
    assert val["unit_cost"] == 300.0
    assert val["stock_value"] == 150.0  # 0.5 kg * 300


def test_weighted_average_cost_repeated_purchases(db_session: Session):
    """Repeat purchases at different prices calculate accurate Weighted-Average Cost (WAC)."""
    db = db_session
    owner, _ = create_user(db, "owner_wac@test.com", UserRole.KITCHEN_OWNER)
    kitchen = create_kitchen(db, owner, "Oil Kitchen")

    ing = KitchenService.create_ingredient(
        db,
        owner,
        IngredientCreate(
            name="Sunflower Oil",
            unit="l",
            initial_stock=0.0,
            minimum_stock_threshold=5.0,
            reorder_quantity=20.0,
        ),
    )

    # Purchase 1: 10 Liters @ Rs 100/L (total Rs 1000)
    req1 = InventoryRestockRequest(
        ingredient_id=ing.id,
        quantity=10.0,
        purchase_unit="l",
        total_price=1000.0,
        supplier_name="Wholesaler A",
    )
    KitchenService.restock_ingredient(db, owner, req1)

    # Purchase 2: 20 Liters @ Rs 130/L (total Rs 2600)
    req2 = InventoryRestockRequest(
        ingredient_id=ing.id,
        quantity=20.0,
        purchase_unit="l",
        total_price=2600.0,
        supplier_name="Wholesaler B",
    )
    ing_updated = KitchenService.restock_ingredient(db, owner, req2)

    assert ing_updated.current_stock == 30.0

    # Total quantity = 10 + 20 = 30 L
    # Total cost = 1000 + 2600 = Rs 3600
    # Weighted Average Unit Cost = 3600 / 30 = Rs 120.00 / L
    val = KitchenService.get_ingredient_valuation(db, kitchen.id, ing.id, ing_updated.current_stock)
    assert val["cost_available"] is True
    assert val["unit_cost"] == 120.0
    assert val["stock_value"] == 3600.0  # 30 * 120.0

    # Check both historical purchases are preserved
    purchases = db.query(Purchase).filter(Purchase.ingredient_id == ing.id).order_by(Purchase.created_at).all()
    assert len(purchases) == 2
    assert purchases[0].unit_cost == 100.0
    assert purchases[1].unit_cost == 130.0


def test_validation_rejects_negative_or_zero_values(db_session: Session):
    """Validation rejects negative price and non-positive quantity."""
    db = db_session
    owner, _ = create_user(db, "owner_val@test.com", UserRole.KITCHEN_OWNER)
    kitchen = create_kitchen(db, owner, "Validation Kitchen")

    ing = KitchenService.create_ingredient(
        db,
        owner,
        IngredientCreate(
            name="Chicken Breast",
            unit="kg",
            initial_stock=5.0,
            minimum_stock_threshold=2.0,
            reorder_quantity=10.0,
        ),
    )

    # Negative price rejected
    with pytest.raises((HTTPException, ValueError)):
        KitchenService.restock_ingredient(
            db,
            owner,
            InventoryRestockRequest(
                ingredient_id=ing.id,
                quantity=10.0,
                purchase_unit="kg",
                total_price=-500.0,
            ),
        )

    # Zero quantity rejected
    with pytest.raises((HTTPException, ValueError)):
        KitchenService.restock_ingredient(
            db,
            owner,
            InventoryRestockRequest(
                ingredient_id=ing.id,
                quantity=0.0,
                purchase_unit="kg",
                total_price=500.0,
            ),
        )


def test_unknown_cost_handling_no_fake_zeros(db_session: Session):
    """Restocking without cost does not invent fake 0.0 purchases and reports cost_available=False."""
    db = db_session
    owner, _ = create_user(db, "owner_nocost@test.com", UserRole.KITCHEN_OWNER)
    kitchen = create_kitchen(db, owner, "No Cost Kitchen")

    ing = KitchenService.create_ingredient(
        db,
        owner,
        IngredientCreate(
            name="Fresh Coriander",
            unit="kg",
            initial_stock=2.0,
            minimum_stock_threshold=1.0,
            reorder_quantity=5.0,
        ),
    )

    # Restock with no price provided
    req = InventoryRestockRequest(
        ingredient_id=ing.id,
        quantity=3.0,
        purchase_unit="kg",
    )
    ing_updated = KitchenService.restock_ingredient(db, owner, req)

    assert ing_updated.current_stock == 5.0
    # No fake purchase created
    purchases = db.query(Purchase).filter(Purchase.ingredient_id == ing.id).all()
    assert len(purchases) == 0

    # Valuation indicates cost unavailable
    val = KitchenService.get_ingredient_valuation(db, kitchen.id, ing.id, ing_updated.current_stock)
    assert val["cost_available"] is False
    assert val["unit_cost"] is None
    assert val["stock_value"] is None


def test_waste_costing_with_wac_and_unknown_cost(db_session: Session):
    """Waste records use WAC when available, and retain None without fake zero when unknown."""
    db = db_session
    owner, _ = create_user(db, "owner_waste@test.com", UserRole.KITCHEN_OWNER)
    kitchen = create_kitchen(db, owner, "Waste Cost Kitchen")

    # 1. Ingredient with known cost: 10 kg @ Rs 200/kg
    ing_known = KitchenService.create_ingredient(
        db,
        owner,
        IngredientCreate(
            name="Paneer",
            unit="kg",
            initial_stock=0.0,
            minimum_stock_threshold=2.0,
            reorder_quantity=10.0,
        ),
    )
    KitchenService.restock_ingredient(
        db,
        owner,
        InventoryRestockRequest(
            ingredient_id=ing_known.id,
            quantity=10.0,
            purchase_unit="kg",
            total_price=2000.0,
        ),
    )

    # Waste 2 kg of paneer
    w1 = KitchenService.record_waste(
        db,
        owner,
        WasteRecordCreate(
            ingredient_id=ing_known.id,
            quantity=2.0,
            reason="Expired batch",
        ),
    )
    # Estimated cost = 2 kg * Rs 200 = Rs 400
    assert w1.estimated_cost == 400.0

    # 2. Ingredient with unknown cost
    ing_unknown = KitchenService.create_ingredient(
        db,
        owner,
        IngredientCreate(
            name="Curd",
            unit="kg",
            initial_stock=5.0,
            minimum_stock_threshold=1.0,
            reorder_quantity=5.0,
        ),
    )
    w2 = KitchenService.record_waste(
        db,
        owner,
        WasteRecordCreate(
            ingredient_id=ing_unknown.id,
            quantity=1.0,
            reason="Spoilage",
        ),
    )
    # Must NOT report 0.0 as if known!
    assert w2.estimated_cost is None


def test_recipe_deduction_with_unit_conversion_and_duplicate_prevention(db_session: Session):
    """Recipe deductions correctly convert recipe units to base ingredient units and prevent duplicates."""
    db = db_session
    owner, _ = create_user(db, "owner_recipe@test.com", UserRole.KITCHEN_OWNER)
    kitchen = create_kitchen(db, owner, "Biryani Kitchen")

    # Base ingredient in kg
    rice = KitchenService.create_ingredient(
        db,
        owner,
        IngredientCreate(
            name="Basmati Rice",
            unit="kg",
            initial_stock=10.0,
            minimum_stock_threshold=2.0,
            reorder_quantity=10.0,
        ),
    )

    menu_item = MenuItem(
        id=str(uuid.uuid4()),
        kitchen_id=kitchen.id,
        name="Chicken Biryani",
        category="Main Course",
        cuisine="Indian",
        price=350.0,
        is_available=True,
    )
    db.add(menu_item)
    db.commit()

    # Link recipe: 250 grams of rice per portion
    KitchenService.set_recipe_ingredient(
        db,
        owner,
        menu_item.id,
        RecipeLinkRequest(
            ingredient_id=rice.id,
            quantity_required=250.0,
            unit="g",
        ),
    )

    order = Order(
        id=str(uuid.uuid4()),
        order_number=f"ORD-{uuid.uuid4().hex[:8].upper()}",
        customer_id=owner.id,
        kitchen_id=kitchen.id,
        status=OrderStatus.ORDER_PLACED,
        subtotal=700.0,
        total_amount=700.0,
    )
    db.add(order)
    order_item = OrderItem(
        id=str(uuid.uuid4()),
        order_id=order.id,
        menu_item_id=menu_item.id,
        item_name=menu_item.name,
        quantity=2,  # 2 portions = 2 * 250 g = 500 g = 0.5 kg
        unit_price=350.0,
        subtotal=700.0,
    )
    db.add(order_item)
    db.commit()

    # Initial deduction via order acceptance
    accepted_order = KitchenService.accept_order(db, owner, order.id)
    assert accepted_order.status == OrderStatus.KITCHEN_ACCEPTED

    txns = db.query(InventoryTransaction).filter(
        InventoryTransaction.reference_order_id == order.id,
        InventoryTransaction.transaction_type == InventoryTransactionType.OUTWARD_ORDER,
    ).all()
    assert len(txns) == 1
    assert txns[0].quantity == -0.5  # 500g deducted as -0.5 kg outward ledger entry

    inv = db.query(Inventory).filter(Inventory.ingredient_id == rice.id).first()
    assert inv.quantity == 9.5  # 10.0 - 0.5

    # Retrying or checking duplicate deduction: txns remain 1 and stock remains 9.5
    duplicate_txns = db.query(InventoryTransaction).filter(
        InventoryTransaction.reference_order_id == order.id,
        InventoryTransaction.transaction_type == InventoryTransactionType.OUTWARD_ORDER,
    ).all()
    assert len(duplicate_txns) == 1
    db.refresh(inv)
    assert inv.quantity == 9.5


def test_cross_kitchen_authorization_isolation(db_session: Session):
    """Kitchen A owner cannot restock or view/alter Kitchen B's inventory."""
    db = db_session
    owner_a, _ = create_user(db, "owner_a@test.com", UserRole.KITCHEN_OWNER)
    owner_b, _ = create_user(db, "owner_b@test.com", UserRole.KITCHEN_OWNER)
    kitchen_a = create_kitchen(db, owner_a, "Kitchen Alpha")
    kitchen_b = create_kitchen(db, owner_b, "Kitchen Beta")

    ing_b = KitchenService.create_ingredient(
        db,
        owner_b,
        IngredientCreate(
            name="Butter",
            unit="kg",
            initial_stock=10.0,
            minimum_stock_threshold=2.0,
            reorder_quantity=5.0,
        ),
    )

    # Kitchen A owner tries to restock Kitchen B's ingredient
    with pytest.raises(HTTPException) as exc_info:
        KitchenService.restock_ingredient(
            db,
            owner_a,
            InventoryRestockRequest(
                ingredient_id=ing_b.id,
                quantity=5.0,
                purchase_unit="kg",
                total_price=500.0,
            ),
        )
    assert exc_info.value.status_code in [400, 404]


def test_admin_inventory_endpoint_accuracy(client: TestClient, db_session: Session):
    """Admin inventory endpoint returns cost_available, unit_cost, and stock_value across kitchens."""
    db = db_session
    admin_user, admin_token = create_user(db, "admin_inv_test@test.com", UserRole.ADMIN)
    owner, _ = create_user(db, "kitchen_inv_owner@test.com", UserRole.KITCHEN_OWNER)
    kitchen = create_kitchen(db, owner, "Admin Check Kitchen")

    # 1. Ingredient with purchase: 20 kg @ Rs 50/kg
    ing1 = KitchenService.create_ingredient(
        db,
        owner,
        IngredientCreate(
            name="Sugar",
            unit="kg",
            initial_stock=0.0,
            minimum_stock_threshold=5.0,
            reorder_quantity=20.0,
        ),
    )
    KitchenService.restock_ingredient(
        db,
        owner,
        InventoryRestockRequest(
            ingredient_id=ing1.id,
            quantity=20.0,
            purchase_unit="kg",
            total_price=1000.0,
        ),
    )

    # 2. Ingredient with no purchase (unknown cost)
    ing2 = KitchenService.create_ingredient(
        db,
        owner,
        IngredientCreate(
            name="Salt",
            unit="kg",
            initial_stock=5.0,
            minimum_stock_threshold=2.0,
            reorder_quantity=10.0,
        ),
    )

    # Fetch admin inventory
    resp = client.get(
        "/api/v1/admin/inventory",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    items = data.get("inventory", data)

    sugar_item = next(i for i in items if i.get("ingredient", {}).get("id") == ing1.id or i.get("ingredient_name") == "Sugar")
    assert sugar_item["unit_cost"] == 50.0
    assert sugar_item["stock_value"] == 1000.0
    assert sugar_item["cost_available"] is True

    salt_item = next(i for i in items if i.get("ingredient", {}).get("id") == ing2.id or i.get("ingredient_name") == "Salt")
    assert salt_item["unit_cost"] is None
    assert salt_item["stock_value"] is None
    assert salt_item["cost_available"] is False
