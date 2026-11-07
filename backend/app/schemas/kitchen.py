"""
Pydantic Schemas for Kitchen Owner Portal Operations:
Dashboard stats, Orders queue & state transitions, Menu management,
Kitchen-defined ingredients, Recipe linking, Inventory ledger,
Restocking recommendations, Waste records, and Kitchen settings.
"""
from datetime import datetime
from typing import List, Optional, Union, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, model_validator
from backend.app.models.enums import (
    OrderStatus,
    PaymentStatus,
    InventoryStatus,
    InventoryTransactionType,
)
from backend.app.schemas.customer import OrderItemResponse, AddressResponse


# 1. Dashboard Statistics
class KitchenDashboardStats(BaseModel):
    kitchen_id: str
    kitchen_name: str
    is_open: bool
    rating: float
    rating_count: int
    pending_orders_count: int
    active_orders_count: int  # ACCEPTED + PREPARING + READY
    completed_orders_today: int
    revenue_today: float
    total_menu_items: int
    low_stock_count: int
    unread_notifications_count: int


# 2. Menu Item Schemas
class MenuItemCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    meal_id: Optional[int] = Field(None, description="Links to meal_info.csv category/cuisine reference")
    description: Optional[str] = None
    category: str = Field(..., min_length=2, max_length=50)  # Beverages, Rice Bowl, Biryani, Pasta, etc.
    cuisine: str = Field(..., min_length=2, max_length=50)   # Indian, Italian, Continental, Thai
    price: float = Field(..., gt=0.0)
    is_available: bool = True
    is_veg: bool = False
    image_url: Optional[str] = None


class MenuItemUpdate(BaseModel):
    name: Optional[str] = None
    meal_id: Optional[int] = None
    description: Optional[str] = None
    category: Optional[str] = None
    cuisine: Optional[str] = None
    price: Optional[float] = Field(None, gt=0.0)
    is_available: Optional[bool] = None
    is_veg: Optional[bool] = None
    image_url: Optional[str] = None


class RecipeIngredientItem(BaseModel):
    ingredient_id: str
    ingredient_name: str
    unit: str
    quantity_required: float

    model_config = ConfigDict(from_attributes=True)


class MenuItemWithRecipeResponse(BaseModel):
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
    created_at: datetime
    recipe_ingredients: List[RecipeIngredientItem] = []

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def prioritize_image(self) -> "MenuItemWithRecipeResponse":
        if self.manual_image_url:
            self.image_url = self.manual_image_url
            self.image_source = "MANUAL"
        return self


class MenuImageUploadRequest(BaseModel):
    image_url: str = Field(..., min_length=5, description="Image URL or data URI")


class MenuImageResponse(BaseModel):
    id: str
    image_url: Optional[str] = None
    image_source: str
    manual_image_url: Optional[str] = None
    message: str


class RecipeLinkRequest(BaseModel):
    ingredient_id: str
    quantity_required: float = Field(..., gt=0.0, description="Kitchen-defined ingredient requirement per food item")
    unit: Optional[str] = Field(default=None, description="Optional unit of requirement (converted to ingredient base unit if different)")


# 3. Ingredient Schemas (Kitchen-defined)
class IngredientCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    unit: str = Field(..., min_length=1, max_length=20, description="g, kg, ml, l, pcs")
    initial_stock: float = Field(default=0.0, ge=0.0)
    minimum_stock_threshold: float = Field(default=10.0, ge=0.0)
    reorder_quantity: float = Field(default=50.0, gt=0.0)
    unit_cost: Optional[float] = Field(default=None, ge=0.0, description="Purchase cost per unit of measurement")
    initial_cost: Optional[float] = Field(default=None, ge=0.0, description="Optional total initial purchase cost for initial stock")
    supplier_name: Optional[str] = Field(default=None, max_length=150)


class IngredientUpdate(BaseModel):
    name: Optional[str] = None
    unit: Optional[str] = None
    minimum_stock_threshold: Optional[float] = Field(None, ge=0.0)
    reorder_quantity: Optional[float] = Field(None, gt=0.0)
    unit_cost: Optional[float] = Field(None, ge=0.0, description="Purchase cost per unit of measurement")


class IngredientResponse(BaseModel):
    id: str
    kitchen_id: str
    name: str
    unit: str
    current_stock: float
    minimum_stock_threshold: float
    reorder_quantity: float
    unit_cost: Optional[float] = None
    stock_value: Optional[float] = None
    cost_available: bool = False
    is_low_stock: bool = False
    status: InventoryStatus = InventoryStatus.AVAILABLE
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):
        instance = super().model_validate(obj, *args, **kwargs)
        if hasattr(obj, 'current_stock') and hasattr(obj, 'minimum_stock_threshold'):
            instance.is_low_stock = obj.current_stock <= obj.minimum_stock_threshold
        return instance




# 4. Inventory Restock & Ledger Schemas
class InventoryRestockRequest(BaseModel):
    ingredient_id: str
    quantity: float = Field(..., gt=0.0, description="Quantity purchased / added")
    purchase_unit: Optional[str] = Field(default=None, description="Unit of the purchase, converted to ingredient base unit if different")
    movement_type: Optional[str] = Field(default="PURCHASE", description="PURCHASE, RETURN, TRANSFER_IN, ADJUSTMENT")
    supplier_name: Optional[str] = Field(default=None, max_length=150)
    invoice_number: Optional[str] = None
    unit_cost: Optional[float] = Field(default=None, ge=0.0, description="Unit cost in purchase unit or base unit")
    total_price: Optional[float] = Field(default=None, ge=0.0, description="Total purchase price paid for the batch")
    total_cost: Optional[float] = Field(default=None, ge=0.0, description="Alias for total_price")
    purchase_date: Optional[datetime] = None
    batch_number: Optional[str] = None
    expiry_date: Optional[datetime] = None
    reason: Optional[str] = None
    notes: Optional[str] = None


class InventoryTransactionResponse(BaseModel):
    id: str
    kitchen_id: str
    ingredient_id: str
    ingredient_name: Optional[str] = None
    transaction_type: InventoryTransactionType
    quantity: float
    balance_after: float
    reference_order_id: Optional[str] = None
    reason: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RestockingRecommendation(BaseModel):
    ingredient_id: str
    ingredient_name: str
    unit: str
    current_stock: float
    expected_usage: float = 0.0
    projected_stock: float = 0.0
    minimum_threshold: float = 0.0
    minimum_stock_threshold: float = 0.0
    short_by: float = 0.0
    restock_needed: float = 0.0
    recommended_reorder_qty: float = 0.0
    recommended_reorder_quantity: float = 0.0
    status: InventoryStatus = InventoryStatus.AVAILABLE
    forecast_status: str = "SUFFICIENT"  # "RESTOCK REQUIRED", "SHORTAGE", "SUFFICIENT"
    urgency_level: str = "NORMAL"  # "CRITICAL", "HIGH", "MEDIUM", "NORMAL"
    urgency: str = "NORMAL"
    unit_cost: Optional[float] = None
    estimated_cost: Optional[float] = None
    cost_available: bool = False

    model_config = ConfigDict(from_attributes=True)


# 5. Waste Records
class WasteRecordCreate(BaseModel):
    ingredient_id: str
    quantity: float = Field(..., gt=0.0)
    reason: str = Field(..., min_length=2, max_length=255, description="e.g. Spoiled, Damaged, Expired")
    notes: Optional[str] = None


class WasteRecordResponse(BaseModel):
    id: str
    kitchen_id: str
    ingredient_id: Optional[str] = None
    ingredient_name: Optional[str] = None
    order_id: Optional[str] = None
    menu_item_id: Optional[str] = None
    menu_item_name: Optional[str] = None
    portions_wasted: Optional[float] = None
    quantity: float
    unit: str
    reason: str
    recorded_by: str
    estimated_cost: Optional[float] = None
    cost_available: bool = True
    source_event: Optional[str] = "MANUAL"
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# 5b. Wastage Analytics Schemas
class WasteByReasonItem(BaseModel):
    reason: str
    count: int
    total_cost: Optional[float] = None
    cost_available: bool = True
    total_quantity: float


class WasteByMenuItem(BaseModel):
    menu_item_name: str
    portions_wasted: float
    estimated_cost: Optional[float] = None
    cost_available: bool = True


class WasteByIngredientItem(BaseModel):
    ingredient_name: str
    quantity: float
    total_quantity: float = 0.0
    unit: str
    unit_cost: Optional[float] = None
    estimated_cost: Optional[float] = None
    cost_available: bool = True


class MonthlyWasteTrendItem(BaseModel):
    month: str
    month_label: str
    total_cost: float
    portions_wasted: float
    count: int


class WasteAnalyticsResponse(BaseModel):
    period_label: str
    total_cost: float
    wasted_orders_count: int
    total_wasted_portions: float
    prepared_food_portions: float
    wastage_rate: float  # Percentage: (wasted_portions / prepared_portions) * 100
    by_reason: List[WasteByReasonItem] = []
    by_menu_item: List[WasteByMenuItem] = []
    by_ingredient: List[WasteByIngredientItem] = []
    monthly_trend: List[MonthlyWasteTrendItem] = []


# 5c. Delivery Route Schemas
class DeliveryLocationInfo(BaseModel):
    name: str
    address: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    phone: Optional[str] = None


class DeliveryRouteResponse(BaseModel):
    order_id: str
    order_number: str
    order_status: OrderStatus
    is_active_delivery: bool
    kitchen: DeliveryLocationInfo
    customer: DeliveryLocationInfo
    distance_km: Optional[float] = None
    duration_minutes: Optional[int] = None
    route_coordinates: Optional[List[List[float]]] = None  # [[lat, lng], ...]
    route_available: bool
    message: Optional[str] = None
    maps_url: Optional[str] = None


# 6. Order Transition Schemas
class OrderRejectRequest(BaseModel):
    rejection_reason: str = Field(..., min_length=3, max_length=255)


class OrderStateTransitionRequest(BaseModel):
    target_status: OrderStatus
    reason: Optional[str] = None


class KitchenOrderResponse(BaseModel):
    id: str
    order_number: str
    customer_id: str
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    status: OrderStatus
    subtotal: float
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
    delivery_address: Optional[Union[AddressResponse, dict, str]] = None
    delivery_address_text: Optional[str] = None
    kitchen_latitude: Optional[float] = None
    kitchen_longitude: Optional[float] = None
    kitchen_address: Optional[str] = None
    delivery_latitude: Optional[float] = None
    delivery_longitude: Optional[float] = None
    delivery_route: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


# 7. Kitchen Settings
class KitchenSettingsUpdate(BaseModel):
    kitchen_name: Optional[str] = Field(None, min_length=2, max_length=150)
    center_id: Optional[int] = None
    description: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    operating_hours: Optional[str] = None
    cuisine: Optional[str] = None
    phone: Optional[str] = None
    is_open: Optional[bool] = None
