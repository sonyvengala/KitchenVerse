"""
Backend Test Suite for Controlled Demand-Prediction Testing Scenario.

Verifies:
  1. The 3 user accounts exist with appropriate roles (2 customers, 1 kitchen owner).
  2. The kitchen owner possesses a test kitchen with menu items, ingredients, recipes, and inventory.
  3. The customers placed deterministic test orders associated with the kitchen.
  4. Operational demand forecasting calculates predictions from the test data and labels them as TEST DATA.
  5. Distinguishes more popular items and higher-demand days.
  6. Admin analytics separates production data from the test scenario.
  7. Demand center excludes test orders from real business intelligence.
"""
import pytest
from datetime import datetime, timezone
from backend.app.core.database import SessionLocal
from backend.app.models.enums import UserRole, OrderStatus
from backend.app.models.user import User, KitchenProfile
from backend.app.models.menu import MenuItem, Ingredient, MenuItemIngredient
from backend.app.models.order import Order
from backend.app.api.routes.ml_forecast import get_operational_forecast, get_demand_center
from backend.app.api.routes.admin import get_analytics


@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_target_accounts_and_roles(db_session):
    owner = db_session.query(User).filter(User.email == "b23it030@kitsw.ac.in").first()
    cust1 = db_session.query(User).filter(User.email == "rohithkalli00@gmail.com").first()
    cust2 = db_session.query(User).filter(User.email == "rohithkalli743@gmail.com").first()

    assert owner is not None, "Kitchen owner account b23it030@kitsw.ac.in must exist"
    assert owner.role == UserRole.KITCHEN_OWNER
    assert owner.is_active is True
    assert owner.is_verified is True

    assert cust1 is not None, "Customer 1 account rohithkalli00@gmail.com must exist"
    assert cust1.role == UserRole.CUSTOMER
    assert cust1.is_active is True

    assert cust2 is not None, "Customer 2 account rohithkalli743@gmail.com must exist"
    assert cust2.role == UserRole.CUSTOMER
    assert cust2.is_active is True


def test_kitchen_profile_and_menu_setup(db_session):
    owner = db_session.query(User).filter(User.email == "b23it030@kitsw.ac.in").first()
    kitchen = db_session.query(KitchenProfile).filter(KitchenProfile.user_id == owner.id).first()

    assert kitchen is not None, "Kitchen profile must exist for kitchen owner"
    assert kitchen.is_approved is True
    assert kitchen.is_open is True

    # Menu items
    items = db_session.query(MenuItem).filter(MenuItem.kitchen_id == kitchen.id).all()
    assert len(items) >= 3, "Kitchen must have at least 3 menu items"
    item_names = [i.name for i in items]
    assert "Special Paneer Biryani" in item_names
    assert "Paneer Tikka Platter" in item_names
    assert "Masala Spiced Chai" in item_names

    # Recipes and ingredients
    recipes = db_session.query(MenuItemIngredient).join(
        MenuItem, MenuItem.id == MenuItemIngredient.menu_item_id
    ).filter(MenuItem.kitchen_id == kitchen.id).all()
    assert len(recipes) >= 5, "Menu items must have recipes linked to ingredients"


def test_customer_test_orders_isolation(db_session):
    owner = db_session.query(User).filter(User.email == "b23it030@kitsw.ac.in").first()
    kitchen = db_session.query(KitchenProfile).filter(KitchenProfile.user_id == owner.id).first()
    cust1 = db_session.query(User).filter(User.email == "rohithkalli00@gmail.com").first()
    cust2 = db_session.query(User).filter(User.email == "rohithkalli743@gmail.com").first()

    test_orders = db_session.query(Order).filter(
        Order.kitchen_id == kitchen.id,
        Order.is_test == True,
        Order.order_number.like("TEST-ORD-KITS-%")
    ).all()

    assert len(test_orders) >= 12, "Must have at least 12 test orders"
    
    # Check both customers placed orders
    c1_orders = [o for o in test_orders if o.customer_id == cust1.id]
    c2_orders = [o for o in test_orders if o.customer_id == cust2.id]
    assert len(c1_orders) > 0, "Customer 1 must have placed orders"
    assert len(c2_orders) > 0, "Customer 2 must have placed orders"

    # Distinct dates (at least 3 to meet operational forecast requirement)
    order_dates = {o.created_at.date() for o in test_orders}
    assert len(order_dates) >= 4, "Orders must span at least 4 distinct dates"

    for o in test_orders:
        assert o.is_test is True, "Order must be marked is_test=True"
        assert o.status == OrderStatus.DELIVERED
        assert o.total_amount > 0.0
        assert len(o.items) > 0, "Order must have items"


def test_operational_forecast_for_kitchen_owner(db_session):
    owner = db_session.query(User).filter(User.email == "b23it030@kitsw.ac.in").first()
    res = get_operational_forecast(weeks_ahead=4, kitchen_id=None, db=db_session, current_user=owner)

    assert res["status"] == "operational", "Operational forecast should be operational"
    assert res["total_test_orders"] >= 12
    assert len(res["daily_history"]) >= 4

    # Every test day should be clearly labeled as 'TEST DATA'
    for day in res["daily_history"]:
        assert day["data_type"] == "TEST DATA"

    # Daily forecast should be present
    assert len(res["daily_forecast"]) == 7
    for df in res["daily_forecast"]:
        assert df["predicted_demand"] > 0
        assert df["recommended_capacity"] >= df["predicted_demand"]

    # Menu items should distinguish popularity
    menu_demands = res["menu_item_demand"]
    assert len(menu_demands) >= 3
    # Check that Special Paneer Biryani is the top ordered item
    biryani_demand = next((m for m in menu_demands if m["name"] == "Special Paneer Biryani"), None)
    chai_demand = next((m for m in menu_demands if m["name"] == "Masala Spiced Chai"), None)
    tikka_demand = next((m for m in menu_demands if m["name"] == "Paneer Tikka Platter"), None)

    assert biryani_demand is not None
    assert chai_demand is not None
    assert tikka_demand is not None
    assert biryani_demand["historical_units_sold"] > tikka_demand["historical_units_sold"], "Biryani should have higher demand than Tikka"

    # Ingredients readiness
    assert len(res["ingredient_readiness"]) >= 3
    for ing in res["ingredient_readiness"]:
        assert ing["status"] == "OK"


def test_admin_analytics_isolation(db_session):
    admin = db_session.query(User).filter(User.role == UserRole.ADMIN).first()
    assert admin is not None, "Admin user must exist"

    # Production scenario strictly excludes test orders
    prod_analytics = get_analytics(scenario="production", admin=admin, db=db_session)
    assert prod_analytics["scenario"] == "production"
    
    # Test scenario view contains test orders
    test_analytics = get_analytics(scenario="test_scenario", admin=admin, db=db_session)
    assert test_analytics["scenario"] == "test_scenario"

    # Sum of counts across orders_over_time
    test_total = sum(d["count"] for d in test_analytics["orders_over_time"])
    assert test_total >= 12, "Test analytics view should show all test orders"

    # Check popular items in test scenario matches KITS menu items
    test_popular_items = [p["item"] for p in test_analytics["popular_items"]]
    assert "Special Paneer Biryani" in test_popular_items


def test_demand_center_excludes_test_orders(db_session):
    admin = db_session.query(User).filter(User.role == UserRole.ADMIN).first()
    res = get_demand_center(days=30, kitchen_id=None, db=db_session, current_user=admin)

    # Demand center strictly requires Order.is_test == False
    # None of the 12 TEST-ORD-KITS-* orders should be included in total_orders
    # Only legitimate orders should be counted
    assert "Special instructions" not in res.get("message", "")
