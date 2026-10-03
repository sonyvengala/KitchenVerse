"""SQLAlchemy models for the Unified Cloud Kitchen Platform."""
import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, String, Boolean, DateTime, Enum, Text, Integer, Float,
    ForeignKey, UniqueConstraint, Index, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database.session import Base


# =============================================
# ENUMS
# =============================================

class UserRole(str, PyEnum):
    CUSTOMER = "CUSTOMER"
    KITCHEN_OWNER = "KITCHEN_OWNER"
    ADMIN = "ADMIN"


class UserStatus(str, PyEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"


class OrderStatus(str, PyEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    PREPARING = "PREPARING"
    READY = "READY"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


class PaymentStatus(str, PyEnum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class AddressType(str, PyEnum):
    HOME = "HOME"
    WORK = "WORK"
    OTHER = "OTHER"


class InventoryTransactionType(str, PyEnum):
    PURCHASE = "PURCHASE"
    USAGE = "USAGE"
    ADJUSTMENT = "ADJUSTMENT"
    WASTE = "WASTE"
    RETURN = "RETURN"


class PromotionType(str, PyEnum):
    PERCENTAGE = "PERCENTAGE"
    FIXED_AMOUNT = "FIXED_AMOUNT"
    FREE_DELIVERY = "FREE_DELIVERY"
    BUY_GET = "BUY_GET"


class NotificationType(str, PyEnum):
    ORDER_UPDATE = "ORDER_UPDATE"
    PROMOTION = "PROMOTION"
    SYSTEM = "SYSTEM"
    REVIEW_REQUEST = "REVIEW_REQUEST"


# =============================================
# USER & AUTH MODELS
# =============================================

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=True)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.CUSTOMER)
    status = Column(Enum(UserStatus), nullable=False, default=UserStatus.PENDING_VERIFICATION)
    is_email_verified = Column(Boolean, nullable=False, default=False)
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    customer_profile = relationship("CustomerProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    kitchen_profile = relationship("KitchenProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    addresses = relationship("Address", back_populates="user", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="customer")
    reviews = relationship("Review", back_populates="user")
    favorites = relationship("Favorite", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")

    __table_args__ = (
        Index("ix_users_email_lower", "email"),
        Index("ix_users_role_status", "role", "status"),
    )


class CustomerProfile(Base):
    __tablename__ = "customer_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    loyalty_points = Column(Integer, nullable=False, default=0)
    total_orders = Column(Integer, nullable=False, default=0)
    total_spent = Column(Float, nullable=False, default=0.0)
    preferences = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="customer_profile")


class KitchenProfile(Base):
    __tablename__ = "kitchen_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    kitchen_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    cuisine_types = Column(JSON, nullable=True)
    is_verified = Column(Boolean, nullable=False, default=False)
    rating = Column(Float, nullable=True)
    total_reviews = Column(Integer, nullable=False, default=0)
    operating_hours = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="kitchen_profile")
    menu_items = relationship("MenuItem", back_populates="kitchen")
    inventory = relationship("Inventory", back_populates="kitchen")
    orders = relationship("Order", back_populates="kitchen")


class Address(Base):
    __tablename__ = "addresses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    address_type = Column(Enum(AddressType), nullable=False, default=AddressType.HOME)
    street = Column(String(255), nullable=False)
    city = Column(String(100), nullable=False)
    state = Column(String(100), nullable=True)
    postal_code = Column(String(20), nullable=False)
    country = Column(String(100), nullable=False, default="US")
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    is_default = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="addresses")


# =============================================
# MENU & INVENTORY MODELS
# =============================================

class MenuItem(Base):
    __tablename__ = "menu_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kitchen_id = Column(UUID(as_uuid=True), ForeignKey("kitchen_profiles.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False)
    category = Column(String(100), nullable=True)
    image_url = Column(String(500), nullable=True)
    is_available = Column(Boolean, nullable=False, default=True)
    is_vegetarian = Column(Boolean, nullable=False, default=False)
    is_vegan = Column(Boolean, nullable=False, default=False)
    is_gluten_free = Column(Boolean, nullable=False, default=False)
    preparation_time_minutes = Column(Integer, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    kitchen = relationship("KitchenProfile", back_populates="menu_items")
    ingredients = relationship("MenuItemIngredient", back_populates="menu_item", cascade="all, delete-orphan")
    order_items = relationship("OrderItem", back_populates="menu_item")

    __table_args__ = (
        Index("ix_menu_items_kitchen_available", "kitchen_id", "is_available"),
    )


class Ingredient(Base):
    __tablename__ = "ingredients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    unit = Column(String(50), nullable=False)
    category = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class MenuItemIngredient(Base):
    __tablename__ = "menu_item_ingredients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    menu_item_id = Column(UUID(as_uuid=True), ForeignKey("menu_items.id", ondelete="CASCADE"), nullable=False)
    ingredient_id = Column(UUID(as_uuid=True), ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False)
    quantity_required = Column(Float, nullable=False)

    menu_item = relationship("MenuItem", back_populates="ingredients")
    ingredient = relationship("Ingredient")

    __table_args__ = (
        UniqueConstraint("menu_item_id", "ingredient_id", name="uq_menu_item_ingredient"),
    )


class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kitchen_id = Column(UUID(as_uuid=True), ForeignKey("kitchen_profiles.id", ondelete="CASCADE"), nullable=False)
    ingredient_id = Column(UUID(as_uuid=True), ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False)
    quantity_on_hand = Column(Float, nullable=False, default=0.0)
    min_quantity = Column(Float, nullable=False, default=0.0)
    max_quantity = Column(Float, nullable=True)
    unit_cost = Column(Float, nullable=False, default=0.0)
    last_restocked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    kitchen = relationship("KitchenProfile", back_populates="inventory")
    ingredient = relationship("Ingredient")
    transactions = relationship("InventoryTransaction", back_populates="inventory")

    __table_args__ = (
        UniqueConstraint("kitchen_id", "ingredient_id", name="uq_kitchen_ingredient"),
    )


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inventory_id = Column(UUID(as_uuid=True), ForeignKey("inventory.id", ondelete="CASCADE"), nullable=False)
    transaction_type = Column(Enum(InventoryTransactionType), nullable=False)
    quantity_change = Column(Float, nullable=False)
    reason = Column(String(255), nullable=True)
    reference_id = Column(UUID(as_uuid=True), nullable=True)
    performed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    inventory = relationship("Inventory", back_populates="transactions")


# =============================================
# ORDER MODELS
# =============================================

class Order(Base):
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    kitchen_id = Column(UUID(as_uuid=True), ForeignKey("kitchen_profiles.id", ondelete="SET NULL"), nullable=True)
    status = Column(Enum(OrderStatus), nullable=False, default=OrderStatus.PENDING)
    subtotal = Column(Float, nullable=False, default=0.0)
    tax_amount = Column(Float, nullable=False, default=0.0)
    delivery_fee = Column(Float, nullable=False, default=0.0)
    discount_amount = Column(Float, nullable=False, default=0.0)
    total_amount = Column(Float, nullable=False, default=0.0)
    delivery_address = Column(JSON, nullable=True)
    special_instructions = Column(Text, nullable=True)
    estimated_delivery_minutes = Column(Integer, nullable=True)
    ordered_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    customer = relationship("User", back_populates="orders")
    kitchen = relationship("KitchenProfile", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payment = relationship("Payment", back_populates="order", uselist=False)

    __table_args__ = (
        Index("ix_orders_customer_status", "customer_id", "status"),
        Index("ix_orders_kitchen_status", "kitchen_id", "status"),
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    menu_item_id = Column(UUID(as_uuid=True), ForeignKey("menu_items.id", ondelete="SET NULL"), nullable=True)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)
    special_instructions = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    order = relationship("Order", back_populates="items")
    menu_item = relationship("MenuItem", back_populates="order_items")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), unique=True, nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(Enum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING)
    payment_method = Column(String(50), nullable=True)
    transaction_id = Column(String(255), nullable=True, unique=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    order = relationship("Order", back_populates="payment")


# =============================================
# CUSTOMER ENGAGEMENT MODELS
# =============================================

class Review(Base):
    __tablename__ = "reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    kitchen_id = Column(UUID(as_uuid=True), ForeignKey("kitchen_profiles.id", ondelete="CASCADE"), nullable=False)
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    is_visible = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="reviews")

    __table_args__ = (
        UniqueConstraint("user_id", "order_id", name="uq_review_per_order"),
    )


class Favorite(Base):
    __tablename__ = "favorites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    menu_item_id = Column(UUID(as_uuid=True), ForeignKey("menu_items.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="favorites")

    __table_args__ = (
        UniqueConstraint("user_id", "menu_item_id", name="uq_favorite_per_user"),
    )


# =============================================
# NOTIFICATION & PROMOTION MODELS
# =============================================

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    notification_type = Column(Enum(NotificationType), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, nullable=False, default=False)
    data = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="notifications")

    __table_args__ = (
        Index("ix_notifications_user_read", "user_id", "is_read"),
    )


class Promotion(Base):
    __tablename__ = "promotions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kitchen_id = Column(UUID(as_uuid=True), ForeignKey("kitchen_profiles.id", ondelete="CASCADE"), nullable=True)
    code = Column(String(50), unique=True, nullable=False)
    promotion_type = Column(Enum(PromotionType), nullable=False)
    discount_value = Column(Float, nullable=False)
    min_order_amount = Column(Float, nullable=True)
    max_discount = Column(Float, nullable=True)
    usage_limit = Column(Integer, nullable=True)
    usage_count = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    starts_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Purchase(Base):
    """Ingredient purchases by kitchens (procurement)."""
    __tablename__ = "purchases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kitchen_id = Column(UUID(as_uuid=True), ForeignKey("kitchen_profiles.id", ondelete="CASCADE"), nullable=False)
    ingredient_id = Column(UUID(as_uuid=True), ForeignKey("ingredients.id", ondelete="SET NULL"), nullable=True)
    supplier_name = Column(String(255), nullable=True)
    quantity = Column(Float, nullable=False)
    unit_cost = Column(Float, nullable=False)
    total_cost = Column(Float, nullable=False)
    purchased_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class WasteRecord(Base):
    __tablename__ = "waste_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kitchen_id = Column(UUID(as_uuid=True), ForeignKey("kitchen_profiles.id", ondelete="CASCADE"), nullable=False)
    ingredient_id = Column(UUID(as_uuid=True), ForeignKey("ingredients.id", ondelete="SET NULL"), nullable=True)
    quantity = Column(Float, nullable=False)
    reason = Column(String(255), nullable=True)
    cost = Column(Float, nullable=False, default=0.0)
    recorded_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class DemandPrediction(Base):
    __tablename__ = "demand_predictions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kitchen_id = Column(UUID(as_uuid=True), ForeignKey("kitchen_profiles.id", ondelete="CASCADE"), nullable=False)
    menu_item_id = Column(UUID(as_uuid=True), ForeignKey("menu_items.id", ondelete="SET NULL"), nullable=True)
    prediction_date = Column(DateTime(timezone=True), nullable=False)
    predicted_demand = Column(Float, nullable=False)
    confidence_score = Column(Float, nullable=True)
    model_version = Column(String(50), nullable=True)
    features = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_demand_predictions_kitchen_date", "kitchen_id", "prediction_date"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=True)
    resource_id = Column(UUID(as_uuid=True), nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="audit_logs")

    __table_args__ = (
        Index("ix_audit_logs_user_action", "user_id", "action"),
        Index("ix_audit_logs_created", "created_at"),
    )
