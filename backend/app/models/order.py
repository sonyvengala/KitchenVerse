"""
Order, OrderItem, Payment, Review, and Favorite models.
Implements normalized relations and supports the order state machine.
"""
from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, Float, Text, Enum, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.app.core.database import Base
from backend.app.models.enums import OrderStatus, PaymentStatus


def utc_now():
    return datetime.now(timezone.utc)


class Order(Base):
    __tablename__ = "orders"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_number = Column(String(32), unique=True, nullable=False, index=True)
    customer_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kitchen_id = Column(String(36), ForeignKey("kitchen_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    delivery_address_id = Column(String(36), ForeignKey("addresses.id", ondelete="SET NULL"), nullable=True)
    delivery_address_text = Column(String(500), nullable=True)
    delivery_address_snapshot = Column(Text, nullable=True)
    delivery_latitude = Column(Float, nullable=True)
    delivery_longitude = Column(Float, nullable=True)
    status = Column(Enum(OrderStatus), default=OrderStatus.ORDER_PLACED, nullable=False, index=True)
    subtotal = Column(Float, nullable=False)
    tax = Column(Float, default=0.0, nullable=False)
    delivery_fee = Column(Float, default=0.0, nullable=False)
    delivery_distance_km = Column(Float, nullable=True)
    pricing_breakdown_json = Column(Text, nullable=True)
    discount_amount = Column(Float, default=0.0, nullable=False)
    promotion_code = Column(String(50), nullable=True)
    is_test = Column(Boolean, default=False, nullable=False)
    total_amount = Column(Float, nullable=False)
    payment_status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False, index=True)
    special_instructions = Column(Text, nullable=True)
    rejection_reason = Column(String(255), nullable=True)
    cancellation_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    customer = relationship("User", foreign_keys=[customer_id], back_populates="orders")
    kitchen = relationship("KitchenProfile", foreign_keys=[kitchen_id], back_populates="orders")
    delivery_address = relationship("Address")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="order", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="order", cascade="all, delete-orphan")
    waste_records = relationship("WasteRecord", back_populates="order", cascade="all, delete-orphan")
    cancellation_requests = relationship("CancellationRequest", back_populates="order", cascade="all, delete-orphan")



class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = Column(String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    menu_item_id = Column(String(36), ForeignKey("menu_items.id", ondelete="SET NULL"), nullable=True, index=True)
    item_name = Column(String(150), nullable=False)
    unit_price = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False)
    subtotal = Column(Float, nullable=False)
    special_requests = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    order = relationship("Order", back_populates="items")
    menu_item = relationship("MenuItem", back_populates="order_items")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = Column(String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    payment_provider = Column(String(50), nullable=False)  # STRIPE, RAZORPAY, CASH, SIMULATED
    transaction_reference = Column(String(100), unique=True, nullable=True, index=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="INR", nullable=False)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False, index=True)
    provider_response_payload = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    order = relationship("Order", back_populates="payments")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = Column(String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kitchen_id = Column(String(36), ForeignKey("kitchen_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    menu_item_id = Column(String(36), ForeignKey("menu_items.id", ondelete="SET NULL"), nullable=True)
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="check_rating_range"),
    )

    order = relationship("Order", back_populates="reviews")
    customer = relationship("User", back_populates="reviews")
    kitchen = relationship("KitchenProfile", back_populates="reviews")
    menu_item = relationship("MenuItem", back_populates="reviews")


class CancellationRequest(Base):
    """
    Tracks admin-assisted cancellation requests for READY orders.
    Customers cannot directly cancel READY orders; they submit a request
    which an Admin reviews and either approves (→ CANCELLED + wastage) or
    rejects (order stays READY, customer notified with reason).
    """
    __tablename__ = "cancellation_requests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = Column(String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kitchen_id = Column(String(36), ForeignKey("kitchen_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    reason = Column(Text, nullable=True)
    customer_note = Column(Text, nullable=True)
    # PENDING | APPROVED | REJECTED
    status = Column(String(20), nullable=False, default="PENDING", index=True)
    admin_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    admin_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    order = relationship("Order", back_populates="cancellation_requests")
    customer = relationship("User", foreign_keys=[customer_id])
    kitchen = relationship("KitchenProfile", foreign_keys=[kitchen_id])
    admin = relationship("User", foreign_keys=[admin_id])

    @property
    def reviewed_by(self):
        return self.admin_id

    @property
    def requested_at(self):
        return self.created_at

    @property
    def reviewed_at(self):
        return self.resolved_at


class Favorite(Base):
    __tablename__ = "favorites"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kitchen_id = Column(String(36), ForeignKey("kitchen_profiles.id", ondelete="CASCADE"), nullable=True, index=True)
    menu_item_id = Column(String(36), ForeignKey("menu_items.id", ondelete="CASCADE"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    user = relationship("User", back_populates="favorites")
    kitchen = relationship("KitchenProfile")
    menu_item = relationship("MenuItem", back_populates="favorites")
