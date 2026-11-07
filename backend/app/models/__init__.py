"""
SQLAlchemy models initialization.
Imports all models so metadata is completely populated for Alembic migrations.
"""
from backend.app.core.database import Base
from backend.app.models.enums import (
    UserRole,
    LicenseStatus,
    OrderStatus,
    PaymentStatus,
    InventoryStatus,
    InventoryTransactionType,
    RealtimeEventType,
)
from backend.app.models.license import (
    KitchenLicense,
    KitchenLicenseDocument,
)
from backend.app.models.user import (
    User,
    Role,
    CustomerProfile,
    KitchenProfile,
    Address,
    UserSession,
)
from backend.app.models.menu import (
    MenuItem,
    Ingredient,
    MenuItemIngredient,
)
from backend.app.models.inventory import (
    Inventory,
    InventoryTransaction,
    Purchase,
    WasteRecord,
)
from backend.app.models.order import (
    Order,
    OrderItem,
    Payment,
    Review,
    Favorite,
    CancellationRequest,
)
from backend.app.models.platform import (
    Notification,
    Promotion,
    ModelVersion,
    DemandPrediction,
    AuditLog,
)

__all__ = [
    "Base",
    "UserRole",
    "LicenseStatus",
    "OrderStatus",
    "PaymentStatus",
    "InventoryStatus",
    "InventoryTransactionType",
    "RealtimeEventType",
    "KitchenLicense",
    "KitchenLicenseDocument",
    "User",
    "Role",
    "CustomerProfile",
    "KitchenProfile",
    "Address",
    "UserSession",
    "MenuItem",
    "Ingredient",
    "MenuItemIngredient",
    "Inventory",
    "InventoryTransaction",
    "Purchase",
    "WasteRecord",
    "Order",
    "OrderItem",
    "Payment",
    "Review",
    "Favorite",
    "CancellationRequest",
    "Notification",
    "Promotion",
    "ModelVersion",
    "DemandPrediction",
    "AuditLog",
]
