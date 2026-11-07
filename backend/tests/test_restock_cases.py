"""
Unit & Integration Tests for Forecast-Aware Restocking Engine

Verifies:
CASE 1: Current stock > minimum, but projected after forecast < minimum
        -> Status: RESTOCK REQUIRED
        -> short_by = minimum_threshold - projected_stock
        -> restock_needed = max(0, expected_usage + minimum_threshold - current_stock)

CASE 2: Projected stock >= minimum
        -> Status: SUFFICIENT
        -> short_by = 0.0

CASE 3: Current stock < forecasted usage
        -> Status: SHORTAGE
        -> short_by = expected_usage - current_stock

Also verifies:
- Configured reorder_quantity is respected without inventing quantities
- Planning calculations NEVER deduct or mutate actual inventory
"""

import pytest
from unittest.mock import MagicMock
from app.services.kitchen_service import KitchenService
from app.models import Ingredient, KitchenProfile, User
from app.schemas.kitchen import RestockingRecommendation


def test_forecast_aware_restock_case_1_restock_required():
    """
    CASE 1:
    Current stock = 6 kg
    Minimum threshold = 5 kg
    Forecasted ingredient usage = 2 kg

    Projected stock = 6 - 2 = 4 kg
    Since 4 kg < 5 kg:
      Status: RESTOCK REQUIRED
      Short by: 5 - 4 = 1 kg
      Restock needed: 2 + 5 - 6 = 1 kg
    """
    db = MagicMock()
    user = MagicMock()
    kitchen = MagicMock()
    kitchen.id = "k-123"

    KitchenService._get_kitchen_profile = MagicMock(return_value=kitchen)

    # Mock ingredient
    ing = Ingredient(
        id="ing-rice",
        kitchen_id="k-123",
        name="Basmati Rice",
        unit="kg",
        current_stock=6.0,
        minimum_stock_threshold=5.0,
        reorder_quantity=10.0,
    )
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [ing]

    # Mock forecasted usage = 2.0 kg
    KitchenService.calculate_forecasted_ingredient_usage = MagicMock(return_value={"ing-rice": 2.0})

    recs = KitchenService.get_restock_recommendations(db, user)
    assert len(recs) == 1
    r = recs[0]

    assert r.current_stock == 6.0
    assert r.expected_usage == 2.0
    assert r.projected_stock == 4.0
    assert r.minimum_threshold == 5.0
    assert r.short_by == 1.0
    assert r.restock_needed == 1.0
    assert r.forecast_status == "RESTOCK REQUIRED"
    # Configured reorder quantity is 10.0, max(10.0, 1.0) = 10.0
    assert r.recommended_reorder_qty == 10.0
    # Ensure inventory was not deducted
    assert ing.current_stock == 6.0


def test_forecast_aware_restock_case_2_sufficient():
    """
    CASE 2:
    Current stock = 10 kg
    Expected usage = 2 kg
    Minimum threshold = 5 kg

    Projected stock = 10 - 2 = 8 kg
    Since 8 kg >= 5 kg:
      Status: SUFFICIENT
      Short by: 0.0
      Restock needed: 0.0
    """
    db = MagicMock()
    user = MagicMock()
    kitchen = MagicMock()
    kitchen.id = "k-123"

    KitchenService._get_kitchen_profile = MagicMock(return_value=kitchen)

    ing = Ingredient(
        id="ing-oil",
        kitchen_id="k-123",
        name="Cooking Oil",
        unit="L",
        current_stock=10.0,
        minimum_stock_threshold=5.0,
        reorder_quantity=5.0,
    )
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [ing]
    KitchenService.calculate_forecasted_ingredient_usage = MagicMock(return_value={"ing-oil": 2.0})

    recs = KitchenService.get_restock_recommendations(db, user)
    assert len(recs) == 1
    r = recs[0]

    assert r.current_stock == 10.0
    assert r.expected_usage == 2.0
    assert r.projected_stock == 8.0
    assert r.minimum_threshold == 5.0
    assert r.short_by == 0.0
    assert r.restock_needed == 0.0
    assert r.forecast_status == "SUFFICIENT"
    assert ing.current_stock == 10.0


def test_forecast_aware_restock_case_3_shortage():
    """
    CASE 3:
    Current stock < forecasted usage
    Current stock = 1.5 kg
    Expected usage = 4.0 kg
    Minimum threshold = 5.0 kg

    Projected stock = 1.5 - 4.0 = -2.5 kg
    Status: SHORTAGE
    Short by: 4.0 - 1.5 = 2.5 kg (immediate shortage for forecast demand)
    Restock needed: 4.0 + 5.0 - 1.5 = 7.5 kg (to cover demand + safety buffer)
    """
    db = MagicMock()
    user = MagicMock()
    kitchen = MagicMock()
    kitchen.id = "k-123"

    KitchenService._get_kitchen_profile = MagicMock(return_value=kitchen)

    ing = Ingredient(
        id="ing-chicken",
        kitchen_id="k-123",
        name="Chicken",
        unit="kg",
        current_stock=1.5,
        minimum_stock_threshold=5.0,
        reorder_quantity=0.0,  # No configured reorder quantity
    )
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [ing]
    KitchenService.calculate_forecasted_ingredient_usage = MagicMock(return_value={"ing-chicken": 4.0})

    recs = KitchenService.get_restock_recommendations(db, user)
    assert len(recs) == 1
    r = recs[0]

    assert r.current_stock == 1.5
    assert r.expected_usage == 4.0
    assert r.projected_stock == -2.5
    assert r.minimum_threshold == 5.0
    assert r.short_by == 2.5
    assert r.restock_needed == 7.5
    assert r.forecast_status == "SHORTAGE"
    # When no reorder_quantity configured, recommended purchase is restock_needed (7.5)
    assert r.recommended_reorder_qty == 7.5
    assert ing.current_stock == 1.5


def test_inventory_separation_guarantee():
    """
    Guarantees that forecasting / restock recommendations NEVER mutate or deduct inventory.
    """
    db = MagicMock()
    user = MagicMock()
    kitchen = MagicMock()
    kitchen.id = "k-123"
    KitchenService._get_kitchen_profile = MagicMock(return_value=kitchen)

    ing = Ingredient(
        id="ing-sugar",
        kitchen_id="k-123",
        name="Sugar",
        unit="kg",
        current_stock=15.0,
        minimum_stock_threshold=10.0,
        reorder_quantity=20.0,
    )
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [ing]
    KitchenService.calculate_forecasted_ingredient_usage = MagicMock(return_value={"ing-sugar": 8.0})

    recs = KitchenService.get_restock_recommendations(db, user)
    assert len(recs) == 1
    assert ing.current_stock == 15.0
    # db.commit and db.add should not have been called for inventory deduction
    assert db.commit.call_count == 0
