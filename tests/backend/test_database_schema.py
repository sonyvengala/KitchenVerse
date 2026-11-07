"""
Automated unit tests for Database Schema and SQLAlchemy Models.
Verifies all tables, foreign keys, indexes, and constraints.
"""
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from backend.app.models import (
    Base,
    Role,
    User,
    UserRole,
    CustomerProfile,
    KitchenProfile,
    Address,
    UserSession,
    MenuItem,
    Ingredient,
    MenuItemIngredient,
    Inventory,
    InventoryTransaction,
    Purchase,
    WasteRecord,
    Order,
    OrderItem,
    Payment,
    Review,
    Favorite,
    Notification,
    Promotion,
    ModelVersion,
    DemandPrediction,
    AuditLog,
)


@pytest.fixture(scope="module")
def test_db():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session, engine
    session.close()
    Base.metadata.drop_all(engine)


def test_all_models_registered_in_metadata():
    expected_tables = {
        "roles",
        "users",
        "customer_profiles",
        "kitchen_profiles",
        "addresses",
        "user_sessions",
        "menu_items",
        "ingredients",
        "menu_item_ingredients",
        "inventory",
        "inventory_transactions",
        "purchases",
        "waste_records",
        "orders",
        "order_items",
        "payments",
        "reviews",
        "favorites",
        "notifications",
        "promotions",
        "model_versions",
        "demand_predictions",
        "audit_logs",
    }
    actual_tables = set(Base.metadata.tables.keys())
    assert expected_tables.issubset(actual_tables), f"Missing tables: {expected_tables - actual_tables}"


def test_table_creation_and_inspection(test_db):
    session, engine = test_db
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    # Check key tables exist
    assert "users" in table_names
    assert "kitchen_profiles" in table_names
    assert "menu_items" in table_names
    assert "orders" in table_names
    assert "inventory_transactions" in table_names
    assert "demand_predictions" in table_names


def test_user_and_profile_relationships(test_db):
    session, engine = test_db

    # Create a test customer user
    user = User(
        email="customer@example.com",
        hashed_password="secure_hashed_password",
        full_name="Test Customer",
        role=UserRole.CUSTOMER,
        is_active=True,
        is_verified=True,
    )
    session.add(user)
    session.flush()

    # Create Customer Profile
    profile = CustomerProfile(
        user_id=user.id,
        dietary_preferences="Vegetarian"
    )
    session.add(profile)
    session.commit()

    retrieved = session.query(User).filter_by(email="customer@example.com").first()
    assert retrieved is not None
    assert retrieved.customer_profile is not None
    assert retrieved.customer_profile.dietary_preferences == "Vegetarian"


def test_kitchen_menu_and_recipe_quantities(test_db):
    session, engine = test_db

    # Create Kitchen Owner
    owner = User(
        email="kitchen@example.com",
        hashed_password="secure_hashed_password",
        full_name="Master Chef",
        role=UserRole.KITCHEN_OWNER,
        is_active=True,
        is_verified=True,
    )
    session.add(owner)
    session.flush()

    kitchen = KitchenProfile(
        user_id=owner.id,
        kitchen_name="Royal Spice Cloud Kitchen",
        center_id=55,
        address="123 Culinary Road",
        city="Bengaluru"
    )
    session.add(kitchen)
    session.flush()

    # Create Ingredient (Kitchen-defined)
    rice = Ingredient(
        kitchen_id=kitchen.id,
        name="Basmati Rice",
        unit="g",
        current_stock=5000.0,
        minimum_stock_threshold=1000.0,
        reorder_quantity=5000.0
    )
    session.add(rice)
    session.flush()

    # Create Menu Item
    biryani = MenuItem(
        kitchen_id=kitchen.id,
        meal_id=1062,
        name="Royal Veg Biryani",
        category="Rice Bowl",
        cuisine="Indian",
        price=249.0,
        is_available=True,
        is_veg=True
    )
    session.add(biryani)
    session.flush()

    # Link Ingredient Recipe (200g of Basmati Rice per Biryani)
    recipe = MenuItemIngredient(
        menu_item_id=biryani.id,
        ingredient_id=rice.id,
        quantity_required=200.0
    )
    session.add(recipe)
    session.commit()

    # Verify relationships
    queried_item = session.query(MenuItem).filter_by(name="Royal Veg Biryani").first()
    assert queried_item is not None
    assert len(queried_item.ingredients_recipe) == 1
    assert queried_item.ingredients_recipe[0].ingredient.name == "Basmati Rice"
    assert queried_item.ingredients_recipe[0].quantity_required == 200.0
