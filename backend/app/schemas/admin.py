"""Admin API schemas - Request/Response models for admin endpoints."""
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, EmailStr


# =============================================
# DASHBOARD
# =============================================

class DashboardStats(BaseModel):
    total_users: int
    customers: int
    kitchen_owners: int
    kitchens: int
    total_orders: int
    pending_orders: int
    completed_orders: int
    cancelled_orders: int
    revenue: float
    low_stock_items: int
    reviews: int
    waste_records: int


# =============================================
# USER MANAGEMENT
# =============================================

class UserSummary(BaseModel):
    id: UUID
    email: str
    first_name: str
    last_name: str
    role: str
    status: str
    is_email_verified: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    users: List[UserSummary]
    total: int
    skip: int
    limit: int


class CustomerProfileSummary(BaseModel):
    id: UUID
    loyalty_points: int
    total_orders: int
    total_spent: float
    
    class Config:
        from_attributes = True


class KitchenProfileSummary(BaseModel):
    id: UUID
    kitchen_name: str
    is_verified: bool
    rating: Optional[float] = None
    
    class Config:
        from_attributes = True


class UserDetailResponse(BaseModel):
    id: UUID
    email: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    role: str
    status: str
    is_email_verified: bool
    email_verified_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    customer_profile: Optional[CustomerProfileSummary] = None
    kitchen_profile: Optional[KitchenProfileSummary] = None
    
    class Config:
        from_attributes = True


class UserStatusUpdate(BaseModel):
    status: str


# =============================================
# KITCHEN MANAGEMENT
# =============================================

class KitchenOwnerSummary(BaseModel):
    id: UUID
    email: str
    first_name: str
    last_name: str
    status: str
    
    class Config:
        from_attributes = True


class KitchenSummary(BaseModel):
    id: UUID
    kitchen_name: str
    description: Optional[str] = None
    is_verified: bool
    rating: Optional[float] = None
    total_reviews: int
    created_at: datetime
    owner: Optional[KitchenOwnerSummary] = None
    
    class Config:
        from_attributes = True


class KitchenListResponse(BaseModel):
    kitchens: List
    total: int
    skip: int
    limit: int


# =============================================
# ORDER MANAGEMENT
# =============================================

class CustomerSummary(BaseModel):
    id: UUID
    email: str
    first_name: str
    last_name: str
    
    class Config:
        from_attributes = True


class PaymentSummary(BaseModel):
    id: UUID
    amount: float
    status: str
    payment_method: Optional[str] = None
    
    class Config:
        from_attributes = True


class OrderSummary(BaseModel):
    id: UUID
    status: str
    total_amount: float
    ordered_at: datetime
    customer: Optional[CustomerSummary] = None
    kitchen: Optional[KitchenSummary] = None
    payment: Optional[PaymentSummary] = None
    
    class Config:
        from_attributes = True


class OrderListResponse(BaseModel):
    orders: List[OrderSummary]
    total: int
    skip: int
    limit: int


# =============================================
# PAYMENT MANAGEMENT
# =============================================

class PaymentDetail(BaseModel):
    id: UUID
    amount: float
    status: str
    payment_method: Optional[str] = None
    transaction_id: Optional[str] = None
    paid_at: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class PaymentListResponse(BaseModel):
    payments: List[PaymentDetail]
    total: int
    skip: int
    limit: int


# =============================================
# INVENTORY MANAGEMENT
# =============================================

class IngredientSummary(BaseModel):
    id: UUID
    name: str
    unit: str
    
    class Config:
        from_attributes = True


class InventoryItem(BaseModel):
    id: UUID
    quantity_on_hand: float
    min_quantity: float
    max_quantity: Optional[float] = None
    unit_cost: Optional[float] = None
    cost_available: bool = False
    stock_value: Optional[float] = None
    last_restocked_at: Optional[datetime] = None
    kitchen: Optional[KitchenSummary] = None
    ingredient: Optional[IngredientSummary] = None
    
    class Config:
        from_attributes = True


class InventoryListResponse(BaseModel):
    inventory: List[InventoryItem]
    total: int
    skip: int
    limit: int


# =============================================
# REVIEWS
# =============================================

class ReviewSummary(BaseModel):
    id: UUID
    rating: int
    comment: Optional[str] = None
    is_visible: bool
    created_at: datetime
    user: Optional[CustomerSummary] = None
    kitchen: Optional[KitchenSummary] = None
    
    class Config:
        from_attributes = True


class ReviewListResponse(BaseModel):
    reviews: List[ReviewSummary]
    total: int
    skip: int
    limit: int


# =============================================
# PROMOTIONS
# =============================================

class PromotionSummary(BaseModel):
    id: UUID
    code: str
    promotion_type: str
    discount_value: float
    is_active: bool
    starts_at: datetime
    expires_at: datetime
    usage_count: int
    usage_limit: Optional[int] = None
    kitchen: Optional[KitchenSummary] = None
    
    class Config:
        from_attributes = True


class PromotionListResponse(BaseModel):
    promotions: List[PromotionSummary]
    total: int
    skip: int
    limit: int


# =============================================
# WASTE MANAGEMENT
# =============================================

class WasteRecordSummary(BaseModel):
    id: UUID
    quantity: float
    reason: Optional[str] = None
    cost: float
    recorded_at: datetime
    kitchen: Optional[KitchenSummary] = None
    ingredient: Optional[IngredientSummary] = None
    
    class Config:
        from_attributes = True


class WasteListResponse(BaseModel):
    waste_records: List[WasteRecordSummary]
    total: int
    skip: int
    limit: int


# =============================================
# DEMAND PREDICTIONS
# =============================================

class MenuItemSummary(BaseModel):
    id: UUID
    name: str
    price: float
    
    class Config:
        from_attributes = True


class DemandPredictionSummary(BaseModel):
    id: UUID
    prediction_date: datetime
    predicted_demand: float
    confidence_score: Optional[float] = None
    model_version: Optional[str] = None
    kitchen: Optional[KitchenSummary] = None
    menu_item: Optional[MenuItemSummary] = None
    
    class Config:
        from_attributes = True


class DemandPredictionListResponse(BaseModel):
    predictions: List[DemandPredictionSummary]
    total: int
    skip: int
    limit: int


# =============================================
# ANALYTICS
# =============================================

class AnalyticsResponse(BaseModel):
    orders_over_time: List[dict]
    revenue_over_time: List[dict]
    order_status: List[dict]
    kitchen_activity: List[dict]
    popular_items: List[dict]
    customer_growth: List[dict]
    inventory_status: dict
    waste_trends: List[dict]


# =============================================
# AUDIT LOGS
# =============================================

class AuditLogSummary(BaseModel):
    id: UUID
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[UUID] = None
    details: Optional[dict] = None
    ip_address: Optional[str] = None
    created_at: datetime
    user: Optional[CustomerSummary] = None
    
    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    logs: List[AuditLogSummary]
    total: int
    skip: int
    limit: int
