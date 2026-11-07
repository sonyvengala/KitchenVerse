"""
MenuItem, Ingredient, and MenuItemIngredient models.
Supports kitchen-defined recipe quantities and ingredient requirement linkage.
"""
from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, Float, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class MenuItem(Base):
    __tablename__ = "menu_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    kitchen_id = Column(String(36), ForeignKey("kitchen_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    meal_id = Column(Integer, nullable=True, index=True)  # Links to meal_info.csv meal_id
    name = Column(String(150), nullable=False, index=True)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=False, index=True)  # e.g., Beverages, Rice Bowl, Starters
    cuisine = Column(String(50), nullable=False, index=True)   # e.g., Indian, Continental, Thai, Italian
    price = Column(Float, nullable=False)
    is_available = Column(Boolean, default=True, nullable=False)
    is_veg = Column(Boolean, default=False, nullable=False)
    image_url = Column(String(500), nullable=True)
    image_source = Column(String(30), default="MANUAL", nullable=False)
    manual_image_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    @property
    def display_image_url(self) -> str | None:
        if self.manual_image_url:
            return self.manual_image_url
        return self.image_url

    # Relationships
    kitchen = relationship("KitchenProfile", back_populates="menu_items")
    ingredients_recipe = relationship("MenuItemIngredient", back_populates="menu_item", cascade="all, delete-orphan")
    order_items = relationship("OrderItem", back_populates="menu_item")
    favorites = relationship("Favorite", back_populates="menu_item", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="menu_item", cascade="all, delete-orphan")


class Ingredient(Base):
    __tablename__ = "ingredients"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    kitchen_id = Column(String(36), ForeignKey("kitchen_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False, index=True)
    unit = Column(String(20), nullable=False)  # g, kg, ml, l, pcs
    current_stock = Column(Float, default=0.0, nullable=False)
    minimum_stock_threshold = Column(Float, default=10.0, nullable=False)
    reorder_quantity = Column(Float, default=50.0, nullable=False)
    unit_cost = Column(Float, nullable=True, default=None)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("kitchen_id", "name", name="uq_kitchen_ingredient_name"),
    )

    kitchen = relationship("KitchenProfile", back_populates="ingredients")
    recipe_links = relationship("MenuItemIngredient", back_populates="ingredient", cascade="all, delete-orphan")
    inventory_record = relationship("Inventory", back_populates="ingredient", uselist=False, cascade="all, delete-orphan")
    transactions = relationship("InventoryTransaction", back_populates="ingredient", cascade="all, delete-orphan")
    purchases = relationship("Purchase", back_populates="ingredient", cascade="all, delete-orphan")
    waste_records = relationship("WasteRecord", back_populates="ingredient", cascade="all, delete-orphan")


class MenuItemIngredient(Base):
    __tablename__ = "menu_item_ingredients"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    menu_item_id = Column(String(36), ForeignKey("menu_items.id", ondelete="CASCADE"), nullable=False, index=True)
    ingredient_id = Column(String(36), ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False, index=True)
    quantity_required = Column(Float, nullable=False)  # e.g. 200.0 (grams) per meal
    unit = Column(String(20), nullable=True)  # Optional unit of requirement
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("menu_item_id", "ingredient_id", name="uq_menu_ingredient"),
    )

    menu_item = relationship("MenuItem", back_populates="ingredients_recipe")
    ingredient = relationship("Ingredient", back_populates="recipe_links")
