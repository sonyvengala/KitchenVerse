"""
Inventory, InventoryTransaction, Purchase, and WasteRecord models.
Maintains strict inventory ledger tracking and prevents unrecorded stock changes.
"""
from datetime import datetime, timezone
from typing import Optional
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Float, Enum, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.app.core.database import Base
from backend.app.models.enums import InventoryStatus, InventoryTransactionType


def utc_now():
    return datetime.now(timezone.utc)


class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    kitchen_id = Column(String(36), ForeignKey("kitchen_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    ingredient_id = Column(String(36), ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False, index=True)
    batch_number = Column(String(50), nullable=True)
    expiry_date = Column(DateTime(timezone=True), nullable=True)
    quantity = Column(Float, default=0.0, nullable=False)
    unit = Column(String(20), nullable=False)
    status = Column(Enum(InventoryStatus), default=InventoryStatus.AVAILABLE, nullable=False, index=True)
    last_updated = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("kitchen_id", "ingredient_id", name="uq_kitchen_ingredient_inventory"),
    )

    kitchen = relationship("KitchenProfile", back_populates="inventory_items")
    ingredient = relationship("Ingredient", back_populates="inventory_record")


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    kitchen_id = Column(String(36), ForeignKey("kitchen_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    ingredient_id = Column(String(36), ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_type = Column(Enum(InventoryTransactionType), nullable=False, index=True)
    quantity = Column(Float, nullable=False)  # positive for inward, negative for outward/waste
    balance_after = Column(Float, nullable=False)
    reference_order_id = Column(String(36), nullable=True, index=True)
    reason = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    kitchen = relationship("KitchenProfile", back_populates="inventory_transactions")
    ingredient = relationship("Ingredient", back_populates="transactions")


class Purchase(Base):
    __tablename__ = "purchases"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    kitchen_id = Column(String(36), ForeignKey("kitchen_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    ingredient_id = Column(String(36), ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False, index=True)
    supplier_name = Column(String(150), nullable=False)
    invoice_number = Column(String(100), nullable=True)
    quantity = Column(Float, nullable=False)
    unit = Column(String(20), nullable=False)
    unit_cost = Column(Float, nullable=False)
    total_cost = Column(Float, nullable=False)
    purchase_date = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    kitchen = relationship("KitchenProfile", back_populates="purchases")
    ingredient = relationship("Ingredient", back_populates="purchases")


class WasteRecord(Base):
    __tablename__ = "waste_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    kitchen_id = Column(String(36), ForeignKey("kitchen_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    ingredient_id = Column(String(36), ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=True, index=True)
    order_id = Column(String(36), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True)
    menu_item_id = Column(String(36), ForeignKey("menu_items.id", ondelete="SET NULL"), nullable=True, index=True)
    menu_item_name = Column(String(150), nullable=True)
    portions_wasted = Column(Float, default=1.0, nullable=True)
    quantity = Column(Float, nullable=False)
    unit = Column(String(20), nullable=False)
    reason = Column(Text, nullable=False)  # e.g., Spoilage, Preparation Error, Expired, CUSTOMER_CANCELLED_AFTER_PREPARATION
    recorded_by = Column(String(100), nullable=False)
    estimated_cost = Column(Float, nullable=True)
    source_event = Column(String(50), default="MANUAL", nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    kitchen = relationship("KitchenProfile", back_populates="waste_records")
    ingredient = relationship("Ingredient", back_populates="waste_records")
    order = relationship("Order", back_populates="waste_records")
    menu_item = relationship("MenuItem")

    @property
    def cost(self) -> Optional[float]:
        return self.estimated_cost
