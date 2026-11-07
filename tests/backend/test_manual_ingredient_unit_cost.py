import uuid
import pytest
from pydantic import ValidationError
from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app.models.user import User, KitchenProfile
from backend.app.models.enums import UserRole
from backend.app.models.menu import Ingredient
from backend.app.core.security import get_password_hash
from backend.app.schemas.kitchen import IngredientCreate, IngredientUpdate
from backend.app.services.kitchen_service import KitchenService


def create_owner_and_kitchen(db: Session, email: str = "cost_owner@test.com") -> tuple[User, KitchenProfile]:
    user = User(
        id=str(uuid.uuid4()),
        email=email,
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Cost Test Owner",
        role=UserRole.KITCHEN_OWNER,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    kitchen = KitchenProfile(
        id=str(uuid.uuid4()),
        user_id=user.id,
        kitchen_name="Cost Valuation Kitchen",
        address="123 Test St",
        city="Bengaluru",
        is_approved=True,
        is_open=True,
    )
    db.add(kitchen)
    db.commit()
    db.refresh(kitchen)
    return user, kitchen


def test_1_add_ingredient_with_unit_cost(db_session: Session):
    """1. Add an ingredient with a unit cost and verify persistence and valuation."""
    owner, kitchen = create_owner_and_kitchen(db_session, "owner1@test.com")

    req = IngredientCreate(
        name="Basmati Rice",
        unit="kg",
        initial_stock=27.0,
        minimum_stock_threshold=5.0,
        reorder_quantity=20.0,
        unit_cost=90.0,
    )
    ing = KitchenService.create_ingredient(db_session, owner, req)
    assert ing.id is not None
    assert ing.unit_cost == 90.0
    assert ing.current_stock == 27.0

    # Verify directly from fresh DB query
    fresh_ing = db_session.query(Ingredient).filter(Ingredient.id == ing.id).first()
    assert fresh_ing is not None
    assert fresh_ing.unit_cost == 90.0

    # Verify valuation: 27 kg * 90/kg = 2430.0
    val = KitchenService.get_ingredient_valuation(db_session, kitchen.id, ing.id)
    assert val["cost_available"] is True
    assert val["unit_cost"] == 90.0
    assert val["stock_value"] == 2430.0


def test_2_and_3_edit_and_save_unit_cost_persists(db_session: Session):
    """2 & 3. Edit and save unit cost, refresh/requery DB to verify cost persists."""
    owner, kitchen = create_owner_and_kitchen(db_session, "owner2@test.com")

    req = IngredientCreate(
        name="Chicken",
        unit="kg",
        initial_stock=20.0,
        minimum_stock_threshold=5.0,
        reorder_quantity=10.0,
        unit_cost=220.0,
    )
    ing = KitchenService.create_ingredient(db_session, owner, req)
    assert ing.unit_cost == 220.0

    val1 = KitchenService.get_ingredient_valuation(db_session, kitchen.id, ing.id)
    assert val1["unit_cost"] == 220.0
    assert val1["stock_value"] == 4400.0  # 20 * 220 = 4400

    # Update unit cost to 250.0
    update_req = IngredientUpdate(
        unit_cost=250.0,
    )
    updated = KitchenService.update_ingredient(db_session, owner, ing.id, update_req)
    assert updated.unit_cost == 250.0

    # Expunge and re-fetch from database to guarantee persistence
    db_session.expire_all()
    fresh = db_session.query(Ingredient).filter(Ingredient.id == ing.id).first()
    assert fresh.unit_cost == 250.0

    # Verify stock value updates: 20 * 250 = 5000.0
    val2 = KitchenService.get_ingredient_valuation(db_session, kitchen.id, ing.id)
    assert val2["cost_available"] is True
    assert val2["unit_cost"] == 250.0
    assert val2["stock_value"] == 5000.0


def test_4_stock_value_calculation_with_decimals(db_session: Session):
    """4. Verify stock value calculation equals actual stock x unit cost with decimal values."""
    owner, kitchen = create_owner_and_kitchen(db_session, "owner4@test.com")

    # 9.45 litres x 150/litre = 1417.50
    req = IngredientCreate(
        name="Oil",
        unit="litres",
        initial_stock=9.45,
        minimum_stock_threshold=2.0,
        reorder_quantity=10.0,
        unit_cost=150.0,
    )
    ing = KitchenService.create_ingredient(db_session, owner, req)

    val = KitchenService.get_ingredient_valuation(db_session, kitchen.id, ing.id)
    assert val["cost_available"] is True
    assert val["unit_cost"] == 150.0
    assert round(val["stock_value"], 2) == 1417.50


def test_5_edit_unit_cost_updates_stock_value(db_session: Session):
    """5. Edit the unit cost and verify the stock value updates accordingly."""
    owner, kitchen = create_owner_and_kitchen(db_session, "owner5@test.com")

    req = IngredientCreate(
        name="Mango Pulp",
        unit="kg",
        initial_stock=10.0,
        unit_cost=100.0,
    )
    ing = KitchenService.create_ingredient(db_session, owner, req)
    assert KitchenService.get_ingredient_valuation(db_session, kitchen.id, ing.id)["stock_value"] == 1000.0

    KitchenService.update_ingredient(db_session, owner, ing.id, IngredientUpdate(unit_cost=125.50))
    val = KitchenService.get_ingredient_valuation(db_session, kitchen.id, ing.id)
    assert val["unit_cost"] == 125.50
    assert val["stock_value"] == 1255.0


def test_6_cost_unset_displays_cost_not_set(db_session: Session):
    """6. Leave cost unset and verify cost_available is False and values are None."""
    owner, kitchen = create_owner_and_kitchen(db_session, "owner6@test.com")

    req = IngredientCreate(
        name="Exotic Herb Blend",
        unit="g",
        initial_stock=500.0,
        unit_cost=None,
    )
    ing = KitchenService.create_ingredient(db_session, owner, req)
    assert ing.unit_cost is None

    val = KitchenService.get_ingredient_valuation(db_session, kitchen.id, ing.id)
    assert val["cost_available"] is False
    assert val["unit_cost"] is None
    assert val["stock_value"] is None

    # Also test setting and then clearing an existing unit_cost to unset
    KitchenService.update_ingredient(db_session, owner, ing.id, IngredientUpdate(unit_cost=10.0))
    assert KitchenService.get_ingredient_valuation(db_session, kitchen.id, ing.id)["cost_available"] is True

    KitchenService.update_ingredient(db_session, owner, ing.id, IngredientUpdate(unit_cost=None))
    val_cleared = KitchenService.get_ingredient_valuation(db_session, kitchen.id, ing.id)
    assert val_cleared["cost_available"] is False
    assert val_cleared["unit_cost"] is None
    assert val_cleared["stock_value"] is None


def test_7_reject_negative_and_invalid_cost_inputs(db_session: Session):
    """7. Reject negative costs on creation and update."""
    owner, kitchen = create_owner_and_kitchen(db_session, "owner7@test.com")

    # Negative cost in Pydantic schema validation
    with pytest.raises(ValidationError):
        IngredientCreate(
            name="Negative Cost Test",
            unit="kg",
            initial_stock=10.0,
            unit_cost=-50.0,
        )

    # Valid ingredient
    req_valid = IngredientCreate(
        name="Valid Ingredient",
        unit="kg",
        initial_stock=10.0,
        unit_cost=50.0,
    )
    ing = KitchenService.create_ingredient(db_session, owner, req_valid)

    # Negative cost on update via Pydantic
    with pytest.raises(ValidationError):
        IngredientUpdate(unit_cost=-1.0)


def test_8_zero_cost_is_valid(db_session: Session):
    """Cost can be zero (e.g. complimentary/free item or sample) and is valid (non-negative)."""
    owner, kitchen = create_owner_and_kitchen(db_session, "owner8@test.com")

    req = IngredientCreate(
        name="Free Sample Sauce",
        unit="ml",
        initial_stock=100.0,
        unit_cost=0.0,
    )
    ing = KitchenService.create_ingredient(db_session, owner, req)
    assert ing.unit_cost == 0.0

    val = KitchenService.get_ingredient_valuation(db_session, kitchen.id, ing.id)
    assert val["cost_available"] is True
    assert val["unit_cost"] == 0.0
    assert val["stock_value"] == 0.0


def test_9_existing_stock_quantities_and_recipe_deductions_unaffected(db_session: Session):
    """8. Confirm existing stock quantities and deductions remain unaffected by unit cost."""
    owner, kitchen = create_owner_and_kitchen(db_session, "owner9@test.com")

    req = IngredientCreate(
        name="Paneer Cubes",
        unit="kg",
        initial_stock=15.0,
        minimum_stock_threshold=3.0,
        reorder_quantity=10.0,
        unit_cost=300.0,
    )
    ing = KitchenService.create_ingredient(db_session, owner, req)
    assert ing.current_stock == 15.0

    # Update stock directly on the ingredient model
    ing.current_stock = 12.5
    db_session.commit()
    db_session.refresh(ing)
    assert ing.current_stock == 12.5
    # Unit cost must still be preserved
    assert ing.unit_cost == 300.0

    # Stock value re-evaluated based on new stock
    val = KitchenService.get_ingredient_valuation(db_session, kitchen.id, ing.id)
    assert val["stock_value"] == 12.5 * 300.0  # 3750.0
