"""
User, Role, CustomerProfile, KitchenProfile, Address, and UserSession models.
"""
from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, Float, Text, Enum
from sqlalchemy.orm import relationship
from backend.app.core.database import Base
from backend.app.models.enums import UserRole


def utc_now():
    return datetime.now(timezone.utc)


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(150), nullable=False)
    phone_number = Column(String(30), nullable=True)
    role = Column(Enum(UserRole), default=UserRole.CUSTOMER, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    verification_token = Column(String(255), nullable=True)
    password_reset_token = Column(String(255), nullable=True)
    password_reset_expires = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    customer_profile = relationship("CustomerProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    kitchen_profile = relationship("KitchenProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    addresses = relationship("Address", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    favorites = relationship("Favorite", back_populates="user", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="customer", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="customer", foreign_keys="[Order.customer_id]", cascade="all, delete-orphan")


class CustomerProfile(Base):
    __tablename__ = "customer_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    dietary_preferences = Column(String(255), nullable=True)  # e.g., Vegetarian, Non-Vegetarian, Vegan
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    user = relationship("User", back_populates="customer_profile")


class KitchenProfile(Base):
    __tablename__ = "kitchen_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    center_id = Column(Integer, nullable=True, index=True)  # Links to fulfilment_center_info.csv center_id
    kitchen_name = Column(String(150), nullable=False, index=True)
    description = Column(Text, nullable=True)
    address = Column(String(255), nullable=False)
    city = Column(String(100), nullable=False)
    state = Column(String(100), default="Karnataka", nullable=True)
    phone = Column(String(30), nullable=True)
    postal_code = Column(String(20), nullable=True)
    operating_hours = Column(String(100), default="09:00 AM - 10:00 PM", nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    cuisine = Column(String(100), nullable=True)
    is_open = Column(Boolean, default=True, nullable=False)
    is_approved = Column(Boolean, default=True, nullable=False)
    approval_status = Column(String(50), default="APPROVED", nullable=False, index=True)
    rejection_reason = Column(String(255), nullable=True)
    rating = Column(Float, default=5.0, nullable=False)
    rating_count = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    user = relationship("User", back_populates="kitchen_profile")
    menu_items = relationship("MenuItem", back_populates="kitchen", cascade="all, delete-orphan")
    ingredients = relationship("Ingredient", back_populates="kitchen", cascade="all, delete-orphan")
    inventory_items = relationship("Inventory", back_populates="kitchen", cascade="all, delete-orphan")
    inventory_transactions = relationship("InventoryTransaction", back_populates="kitchen", cascade="all, delete-orphan")
    purchases = relationship("Purchase", back_populates="kitchen", cascade="all, delete-orphan")
    waste_records = relationship("WasteRecord", back_populates="kitchen", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="kitchen", foreign_keys="[Order.kitchen_id]")
    reviews = relationship("Review", back_populates="kitchen")
    license = relationship("KitchenLicense", back_populates="kitchen", uselist=False, cascade="all, delete-orphan")


class Address(Base):
    __tablename__ = "addresses"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    address_line1 = Column(String(255), nullable=False)
    address_line2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=False)
    state = Column(String(100), nullable=False)
    postal_code = Column(String(20), nullable=False)
    landmark = Column(String(150), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    label = Column(String(50), default="Home", nullable=True)  # Home, Work, Other
    delivery_instructions = Column(String(500), nullable=True)
    is_default = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    user = relationship("User", back_populates="addresses")


class UserSession(Base):
    __tablename__ = "user_sessions"

    session_id = Column(String(128), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    is_revoked = Column(Boolean, default=False, nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    user = relationship("User", back_populates="sessions")
