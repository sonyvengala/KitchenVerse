"""
Pydantic Schemas for Customer Portal Operations:
Browsing, Menu, Cart, Orders, Checkout, Reviews, Favorites, and Addresses.
"""
from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, ConfigDict, model_validator
from backend.app.models.enums import OrderStatus, PaymentStatus


class AddressCreate(BaseModel):
    address_line1: str = Field(..., min_length=3, max_length=255)
    address_line2: Optional[str] = None
    city: str = Field(..., min_length=2, max_length=100)
    state: str = Field(..., min_length=2, max_length=100)
    postal_code: str = Field(..., min_length=3, max_length=20)
    landmark: Optional[str] = Field(None, max_length=150)
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    label: Optional[str] = Field("Home", max_length=50)  # Home, Work, Other
    delivery_instructions: Optional[str] = Field(None, max_length=500)
    is_default: bool = False

    @model_validator(mode="after")
    def validate_coordinates(self) -> "AddressCreate":
        if (self.latitude is None and self.longitude is not None) or (self.latitude is not None and self.longitude is None):
            raise ValueError("Both latitude and longitude must be provided together.")
        return self


class AddressUpdate(BaseModel):
    address_line1: Optional[str] = Field(None, min_length=3, max_length=255)
    address_line2: Optional[str] = None
    city: Optional[str] = Field(None, min_length=2, max_length=100)
    state: Optional[str] = Field(None, min_length=2, max_length=100)
    postal_code: Optional[str] = Field(None, min_length=3, max_length=20)
    landmark: Optional[str] = Field(None, max_length=150)
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    label: Optional[str] = Field(None, max_length=50)
    delivery_instructions: Optional[str] = Field(None, max_length=500)
    is_default: Optional[bool] = None

    @model_validator(mode="after")
    def validate_coordinates(self) -> "AddressUpdate":
        if (self.latitude is None and self.longitude is not None) or (self.latitude is not None and self.longitude is None):
            raise ValueError("Both latitude and longitude must be provided together.")
        return self


class AddressResponse(BaseModel):
    id: str
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: str
    postal_code: str
    landmark: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    label: Optional[str] = "Home"
    delivery_instructions: Optional[str] = None
    is_default: bool

    model_config = ConfigDict(from_attributes=True)


class CustomerProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    dietary_preferences: Optional[str] = None


class MenuItemPublic(BaseModel):
    id: str
    kitchen_id: str
    meal_id: Optional[int] = None
    name: str
    description: Optional[str] = None
    category: str
    cuisine: str
    price: float
    is_available: bool
    is_veg: bool
    image_url: Optional[str] = None
    image_source: Optional[str] = "MANUAL"
    manual_image_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def prioritize_image(self) -> "MenuItemPublic":
        if self.manual_image_url:
            self.image_url = self.manual_image_url
            self.image_source = "MANUAL"
        return self


class UpdateDeliveryLocationRequest(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    address_text: Optional[str] = None


class KitchenPublic(BaseModel):
    id: str
    kitchen_name: str
    center_id: Optional[int] = None
    description: Optional[str] = None
    address: str
    city: str
    phone: Optional[str] = None
    postal_code: Optional[str] = None
    operating_hours: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    cuisine: Optional[str] = None
    is_open: bool
    rating: float
    rating_count: int
    distance_km: Optional[float] = None
    distance_type: Optional[str] = None
    is_estimate: Optional[bool] = False
    duration_minutes: Optional[int] = None
    can_deliver: bool = True

    model_config = ConfigDict(from_attributes=True)


class KitchenDetailResponse(KitchenPublic):
    menu_items: List[MenuItemPublic] = []


class CartItemRequest(BaseModel):
    menu_item_id: str
    quantity: int = Field(..., gt=0)
    special_requests: Optional[str] = None


class CheckoutPreviewRequest(BaseModel):
    kitchen_id: str
    items: List[CartItemRequest]
    delivery_address_id: Optional[str] = None
    promo_code: Optional[str] = None
    promotion_code: Optional[str] = None


class CheckoutPreviewResponse(BaseModel):
    kitchen_id: str
    items_count: int
    subtotal: float
    discount_amount: float = 0.0
    applied_promo: Optional[str] = None
    applied_promotion_code: Optional[str] = None
    tax: float
    delivery_fee: float
    total_amount: float
    currency: str = "INR"
    available: bool = True
    unavailable_items: List[str] = []
    # Dynamic delivery pricing breakdown fields
    distance_km: Optional[float] = None
    distance_type: Optional[str] = None  # "driving" | "estimated_straight_line"
    is_estimate: bool = False
    distance_label: Optional[str] = None
    base_delivery_fee: float = 20.0
    distance_fee: float = 0.0
    surge_fee: float = 0.0
    platform_fee: float = 0.0
    formula_display: Optional[str] = None
    requires_location: bool = False
    out_of_range: bool = False
    max_delivery_radius_km: Optional[float] = None
    pricing_breakdown: Optional[Dict[str, Any]] = None


class OrderCreateRequest(BaseModel):
    kitchen_id: str
    items: List[CartItemRequest] = Field(..., min_length=1)
    delivery_address_id: Optional[str] = None
    payment_method: str = "CASH"  # CASH, SIMULATED, STRIPE, RAZORPAY
    special_instructions: Optional[str] = None
    promo_code: Optional[str] = None
    promotion_code: Optional[str] = None


class OrderItemResponse(BaseModel):
    id: str
    menu_item_id: Optional[str] = None
    item_name: str
    unit_price: float
    quantity: int
    subtotal: float
    total_price: Optional[float] = None
    special_requests: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

    def model_post_init(self, __context: Any) -> None:
        if self.total_price is None:
            self.total_price = self.subtotal


class CancellationRequestCreate(BaseModel):
    """Customer submits a cancellation request for a READY order."""
    reason: Optional[str] = Field(None, max_length=500)
    customer_note: Optional[str] = Field(None, max_length=1000)


class CancellationRequestResponse(BaseModel):
    """Response shape for a cancellation request (customer or admin view)."""
    id: str
    order_id: str
    customer_id: str
    kitchen_id: str
    reason: Optional[str] = None
    customer_note: Optional[str] = None
    status: str  # PENDING | APPROVED | REJECTED
    admin_id: Optional[str] = None
    reviewed_by: Optional[str] = None
    admin_note: Optional[str] = None
    created_at: datetime
    requested_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AdminCancellationDecision(BaseModel):
    """Admin approves or rejects a cancellation request."""
    decision: str  # APPROVED | REJECTED
    admin_note: Optional[str] = Field(None, max_length=500)


class OrderDetailResponse(BaseModel):
    id: str
    order_number: str
    kitchen_id: str
    kitchen_name: Optional[str] = None
    status: OrderStatus
    subtotal: float
    discount_amount: float = 0.0
    promotion_code: Optional[str] = None
    tax: float
    delivery_fee: float
    total_amount: float
    payment_status: PaymentStatus
    special_instructions: Optional[str] = None
    rejection_reason: Optional[str] = None
    cancellation_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemResponse] = []
    delivery_address: Optional[AddressResponse] = None
    delivery_address_text: Optional[str] = None
    delivery_latitude: Optional[float] = None
    delivery_longitude: Optional[float] = None
    delivery_distance_km: Optional[float] = None
    pricing_breakdown_json: Optional[str] = None
    pricing_breakdown: Optional[Dict[str, Any]] = None
    can_cancel: Optional[bool] = None
    cancellation_warning: Optional[str] = None
    cancellation_request: Optional[CancellationRequestResponse] = None

    model_config = ConfigDict(from_attributes=True)


class PromotionPublic(BaseModel):
    id: str
    code: str
    title: str
    description: Optional[str] = None
    discount_percentage: float
    discount_amount: float
    minimum_order_amount: float
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class FavoriteToggleRequest(BaseModel):
    kitchen_id: Optional[str] = None
    menu_item_id: Optional[str] = None


class ReviewCreateRequest(BaseModel):
    order_id: str
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None
    menu_item_id: Optional[str] = None


class NotificationResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    title: str
    message: str
    event_type: str
    notification_type: Optional[str] = None
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    def model_post_init(self, __context: Any) -> None:
        if self.notification_type is None:
            self.notification_type = self.event_type
