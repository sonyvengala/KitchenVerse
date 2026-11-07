"""
Kitchen Owner Portal API Endpoints — Phase 4.
All routes are RBAC-protected by require_kitchen_owner dependency.
Kitchen owners can ONLY access their own kitchen's data.
"""
from typing import List, Optional
from datetime import datetime, timezone
import os
import hashlib
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.core.database import get_db
from backend.app.core.deps import require_kitchen_owner, require_kitchen_or_admin
from backend.app.models.enums import OrderStatus, LicenseStatus, UserRole
from backend.app.models.license import KitchenLicense, KitchenLicenseDocument
from backend.app.models.user import User
from backend.app.services.fssai_service import FssaiService, SECURE_LICENSES_DIR, utc_now
from backend.app.schemas.license import (
    LicenseOcrScanResponse,
    KitchenLicenseResponse,
    KitchenLicenseDocumentResponse,
    LicenseSubmissionRequest,
    LicenseRenewalRequest,
)
from backend.app.schemas.kitchen import (
    KitchenDashboardStats,
    MenuItemCreate,
    MenuItemUpdate,
    MenuItemWithRecipeResponse,
    IngredientCreate,
    IngredientUpdate,
    IngredientResponse,
    InventoryRestockRequest,
    InventoryTransactionResponse,
    WasteRecordCreate,
    WasteRecordResponse,
    WasteAnalyticsResponse,
    DeliveryRouteResponse,
    OrderRejectRequest,
    OrderStateTransitionRequest,
    KitchenOrderResponse,
    KitchenSettingsUpdate,
    RestockingRecommendation,
    RecipeLinkRequest,
    MenuImageUploadRequest,
    MenuImageResponse,
)
from backend.app.schemas.customer import NotificationResponse
from backend.app.services.kitchen_service import KitchenService

router = APIRouter(prefix="/kitchen", tags=["Kitchen Owner Portal"])


# ── Dashboard ─────────────────────────────────────────────────────────────────
@router.get("/dashboard", response_model=KitchenDashboardStats)
def get_dashboard(
    current_user: User = Depends(require_kitchen_owner),
    db: Session = Depends(get_db),
):
    """Real-time kitchen dashboard statistics. No fabricated data."""
    return KitchenService.get_dashboard_stats(db, current_user)


# ── Order Queue ───────────────────────────────────────────────────────────────
@router.get("/orders", response_model=List[KitchenOrderResponse])
def get_orders(
    order_status: Optional[str] = Query(None, description="Comma-separated order statuses to filter"),
    current_user: User = Depends(require_kitchen_owner),
    db: Session = Depends(get_db),
):
    """Retrieve kitchen order queue. Optionally filter by comma-separated status values."""
    status_filter = None
    if order_status:
        try:
            status_filter = [OrderStatus(s.strip()) for s in order_status.split(",")]
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid order status: {exc}")
    orders = KitchenService.get_order_queue(db, current_user, status_filter)
    return [_serialize_kitchen_order(o) for o in orders]


@router.get("/orders/{order_id}", response_model=KitchenOrderResponse)
def get_order(
    order_id: str,
    current_user: User = Depends(require_kitchen_owner),
    db: Session = Depends(get_db),
):
    """Get details of a specific kitchen order."""
    order = KitchenService.get_single_order(db, current_user, order_id)
    return _serialize_kitchen_order(order)


@router.get("/orders/{order_id}/delivery-route", response_model=DeliveryRouteResponse)
def get_order_delivery_route(
    order_id: str,
    current_user: User = Depends(require_kitchen_owner),
    db: Session = Depends(get_db),
):
    """Retrieve real delivery route and location information for a specific kitchen order."""
    return KitchenService.get_delivery_route(db, current_user, order_id)


@router.post("/orders/{order_id}/accept", response_model=KitchenOrderResponse)
def accept_order(
    order_id: str,
    current_user: User = Depends(require_kitchen_owner),
    db: Session = Depends(get_db),
):
    """Accept an incoming order and trigger inventory consumption for recipe items."""
    order = KitchenService.accept_order(db, current_user, order_id)
    return _serialize_kitchen_order(order)


@router.post("/orders/{order_id}/reject", response_model=KitchenOrderResponse)
def reject_order(
    order_id: str,
    req: OrderRejectRequest,
    current_user: User = Depends(require_kitchen_owner),
    db: Session = Depends(get_db),
):
    """Reject an incoming order with a mandatory rejection reason."""
    order = KitchenService.reject_order(db, current_user, order_id, req.rejection_reason)
    return _serialize_kitchen_order(order)


@router.post("/orders/{order_id}/transition", response_model=KitchenOrderResponse)
def transition_order(
    order_id: str,
    req: OrderStateTransitionRequest,
    current_user: User = Depends(require_kitchen_owner),
    db: Session = Depends(get_db),
):
    """
    Advance an order through the kitchen state machine.
    Valid transitions:
      KITCHEN_ACCEPTED -> PREPARING
      PREPARING        -> READY
      READY            -> OUT_FOR_DELIVERY | DELIVERED
    """
    order = KitchenService.transition_order_status(db, current_user, order_id, req.target_status, req.reason)
    return _serialize_kitchen_order(order)


# ── Menu Management ───────────────────────────────────────────────────────────
@router.get("/menu", response_model=List[MenuItemWithRecipeResponse])
def list_menu_items(
    current_user: User = Depends(require_kitchen_owner),
    db: Session = Depends(get_db),
):
    """List all menu items for this kitchen, including recipe ingredient links."""
    items = KitchenService.list_menu_items(db, current_user)
    return [_serialize_menu_item_with_recipe(item) for item in items]


@router.post("/menu", response_model=MenuItemWithRecipeResponse, status_code=status.HTTP_201_CREATED)
def create_menu_item(
    req: MenuItemCreate,
    current_user: User = Depends(require_kitchen_owner),
    db: Session = Depends(get_db),
):
    """Create a new menu item for this kitchen."""
    item = KitchenService.create_menu_item(db, current_user, req)
    return _serialize_menu_item_with_recipe(item)


@router.put("/menu/{item_id}", response_model=MenuItemWithRecipeResponse)
def update_menu_item(
    item_id: str,
    req: MenuItemUpdate,
    current_user: User = Depends(require_kitchen_owner),
    db: Session = Depends(get_db),
):
    """Update an existing menu item."""
    item = KitchenService.update_menu_item(db, current_user, item_id, req)
    return _serialize_menu_item_with_recipe(item)


@router.delete("/menu/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_menu_item(
    item_id: str,
    current_user: User = Depends(require_kitchen_owner),
    db: Session = Depends(get_db),
):
    """Delete a menu item from this kitchen."""
    KitchenService.delete_menu_item(db, current_user, item_id)



@router.post("/menu/{item_id}/upload-image", response_model=MenuItemWithRecipeResponse)
async def upload_menu_item_image(
    item_id: str,
    request: Request,
    current_user: User = Depends(require_kitchen_owner),
    db: Session = Depends(get_db),
):
    """Set or replace manual image for this menu item (supports multipart file upload and JSON/form image_url)."""
    content_type = request.headers.get("content-type", "").lower()
    if "multipart/form-data" in content_type:
        form = await request.form()
        file = form.get("file")
        image_url = form.get("image_url")
        if file and hasattr(file, "read"):
            file_content = await file.read()
            item = KitchenService.upload_menu_item_image_file(
                db, current_user, item_id, file_content, getattr(file, "filename", "uploaded.jpg") or "uploaded.jpg", getattr(file, "content_type", None)
            )
            return _serialize_menu_item_with_recipe(item)
        elif image_url and isinstance(image_url, str):
            item = KitchenService.upload_menu_item_image(db, current_user, item_id, image_url)
            return _serialize_menu_item_with_recipe(item)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file or image_url provided.")
    elif "application/json" in content_type:
        body = await request.json()
        image_url = body.get("image_url")
        if not image_url or not isinstance(image_url, str):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="image_url is required.")
        item = KitchenService.upload_menu_item_image(db, current_user, item_id, image_url)
        return _serialize_menu_item_with_recipe(item)
    else:
        try:
            body = await request.json()
            image_url = body.get("image_url")
            if image_url:
                item = KitchenService.upload_menu_item_image(db, current_user, item_id, image_url)
                return _serialize_menu_item_with_recipe(item)
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported content type. Provide multipart/form-data with a file or application/json with image_url."
        )


@router.delete("/menu/{item_id}/image", response_model=MenuItemWithRecipeResponse)
def remove_menu_item_image(
    item_id: str,
    current_user: User = Depends(require_kitchen_owner),
    db: Session = Depends(get_db),
):
    """Remove manual image from menu item."""
    item = KitchenService.remove_menu_item_image(db, current_user, item_id)
    return _serialize_menu_item_with_recipe(item)


# ── Recipe Links ──────────────────────────────────────────────────────────────
@router.post("/menu/{item_id}/recipe", status_code=status.HTTP_201_CREATED)
def link_recipe_ingredient(
    item_id: str,
    req: RecipeLinkRequest,
    current_user: User = Depends(require_kitchen_owner),
    db: Session = Depends(get_db),
):
    """Link a kitchen ingredient to a menu item with defined quantity requirement."""
    link = KitchenService.set_recipe_ingredient(db, current_user, item_id, req)
    return {"menu_item_id": link.menu_item_id, "ingredient_id": link.ingredient_id, "quantity_required": link.quantity_required}


@router.delete("/menu/{item_id}/recipe/{ingredient_id}", status_code=status.HTTP_204_NO_CONTENT)
def unlink_recipe_ingredient(
    item_id: str,
    ingredient_id: str,
    current_user: User = Depends(require_kitchen_owner),
    db: Session = Depends(get_db),
):
    """Remove a recipe ingredient link from a menu item."""
    KitchenService.remove_recipe_ingredient(db, current_user, item_id, ingredient_id)


# ── Ingredients ───────────────────────────────────────────────────────────────
@router.get("/ingredients", response_model=List[IngredientResponse])
def list_ingredients(
    current_user: User = Depends(require_kitchen_owner),
    db: Session = Depends(get_db),
):
    """List all kitchen-defined ingredients and their current stock levels."""
    return KitchenService.list_ingredients(db, current_user)


@router.post("/ingredients", response_model=IngredientResponse, status_code=status.HTTP_201_CREATED)
def create_ingredient(
    req: IngredientCreate,
    current_user: User = Depends(require_kitchen_owner),
    db: Session = Depends(get_db),
):
    """Create a new ingredient with initial stock. Automatically creates inventory record and transaction."""
    return KitchenService.create_ingredient(db, current_user, req)


@router.put("/ingredients/{ingredient_id}", response_model=IngredientResponse)
def update_ingredient(
    ingredient_id: str,
    req: IngredientUpdate,
    current_user: User = Depends(require_kitchen_owner),
    db: Session = Depends(get_db),
):
    """Update ingredient metadata (name, unit, thresholds)."""
    return KitchenService.update_ingredient(db, current_user, ingredient_id, req)


@router.delete("/ingredients/{ingredient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ingredient(
    ingredient_id: str,
    current_user: User = Depends(require_kitchen_owner),
    db: Session = Depends(get_db),
):
    """Delete an ingredient. Fails if ingredient is linked to any menu item recipes."""
    KitchenService.delete_ingredient(db, current_user, ingredient_id)


# ── Inventory Ledger ──────────────────────────────────────────────────────────
@router.post("/inventory/restock", response_model=IngredientResponse)
def restock_ingredient(
    req: InventoryRestockRequest,
    current_user: User = Depends(require_kitchen_owner),
    db: Session = Depends(get_db),
):
    """Restock an ingredient: add quantity, log INWARD transaction and purchase record."""
    return KitchenService.restock_ingredient(db, current_user, req)


@router.get("/inventory/transactions", response_model=List[InventoryTransactionResponse])
def get_inventory_transactions(
    ingredient_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(require_kitchen_owner),
    db: Session = Depends(get_db),
):
    """Retrieve inventory transaction ledger for this kitchen. Optionally filter by ingredient."""
    txns = KitchenService.get_inventory_transactions(db, current_user, ingredient_id, limit)
    return [_serialize_transaction(t) for t in txns]


@router.get("/inventory/recommendations", response_model=List[RestockingRecommendation])
def get_restock_recommendations(
    include_all: bool = Query(False),
    status: Optional[str] = Query(None),
    current_user: User = Depends(require_kitchen_owner),
    db: Session = Depends(get_db),
):
    """Get restocking recommendations for low-stock ingredients sorted by urgency."""
    recs = KitchenService.get_restock_recommendations(db, current_user)
    if status:
        return [r for r in recs if (r.forecast_status or "").upper() == status.upper()]
    if not include_all:
        return [
            r for r in recs
            if r.forecast_status != "SUFFICIENT"
            or r.restock_needed > 0
            or r.current_stock <= r.minimum_stock_threshold
        ]
    return recs


# ── Waste Records ─────────────────────────────────────────────────────────────
@router.post("/waste", response_model=WasteRecordResponse, status_code=status.HTTP_201_CREATED)
def record_waste(
    req: WasteRecordCreate,
    current_user: User = Depends(require_kitchen_owner),
    db: Session = Depends(get_db),
):
    """Record ingredient waste. Deducts from inventory and logs WASTE transaction."""
    waste = KitchenService.record_waste(db, current_user, req)
    return _serialize_waste(waste)


@router.get("/waste", response_model=List[WasteRecordResponse])
def get_waste_records(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_kitchen_owner),
    db: Session = Depends(get_db),
):
    """Retrieve waste records for this kitchen."""
    records = KitchenService.get_waste_records(db, current_user, limit)
    return [_serialize_waste(w) for w in records]


@router.get("/waste/analytics", response_model=WasteAnalyticsResponse)
def get_waste_analytics(
    year: Optional[int] = Query(None, description="Year (e.g. 2026)"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Month (1-12)"),
    current_user: User = Depends(require_kitchen_owner),
    db: Session = Depends(get_db),
):
    """Retrieve wastage analytics for this kitchen for a specific month/year."""
    return KitchenService.get_waste_analytics(db, current_user, year=year, month=month)


# ── Kitchen Settings ──────────────────────────────────────────────────────────
@router.get("/settings")
@router.get("/profile")
def get_kitchen_settings(
    current_user: User = Depends(require_kitchen_owner),
    db: Session = Depends(get_db),
):
    """Retrieve full kitchen profile and operating settings."""
    kitchen = KitchenService._get_kitchen_profile(db, current_user, require_approved=False)
    return {
        "id": kitchen.id,
        "kitchen_name": kitchen.kitchen_name,
        "center_id": kitchen.center_id,
        "description": kitchen.description,
        "address": kitchen.address,
        "city": kitchen.city,
        "state": getattr(kitchen, "state", "Karnataka") or "Karnataka",
        "postal_code": getattr(kitchen, "postal_code", None),
        "phone": kitchen.phone,
        "operating_hours": getattr(kitchen, "operating_hours", "09:00 AM - 10:00 PM"),
        "cuisine": getattr(kitchen, "cuisine", "Multi-Cuisine"),
        "latitude": getattr(kitchen, "latitude", None),
        "longitude": getattr(kitchen, "longitude", None),
        "is_open": kitchen.is_open,
        "is_approved": kitchen.is_approved,
        "approval_status": getattr(kitchen, "approval_status", "APPROVED" if kitchen.is_approved else "PENDING_APPROVAL"),
        "rejection_reason": getattr(kitchen, "rejection_reason", None),
        "rating": kitchen.rating,
        "rating_count": kitchen.rating_count,
        "updated_at": kitchen.updated_at,
    }


@router.put("/settings")
def update_settings(
    req: KitchenSettingsUpdate,
    current_user: User = Depends(require_kitchen_owner),
    db: Session = Depends(get_db),
):
    """Update kitchen settings (name, open/close, description, address, location coordinates, etc.)."""
    kitchen = KitchenService.update_settings(db, current_user, req)
    return {
        "id": kitchen.id,
        "kitchen_name": kitchen.kitchen_name,
        "center_id": kitchen.center_id,
        "description": kitchen.description,
        "address": kitchen.address,
        "city": kitchen.city,
        "state": getattr(kitchen, "state", "Karnataka") or "Karnataka",
        "postal_code": getattr(kitchen, "postal_code", None),
        "phone": kitchen.phone,
        "operating_hours": getattr(kitchen, "operating_hours", None),
        "cuisine": getattr(kitchen, "cuisine", None),
        "latitude": getattr(kitchen, "latitude", None),
        "longitude": getattr(kitchen, "longitude", None),
        "is_open": kitchen.is_open,
        "is_approved": kitchen.is_approved,
        "approval_status": getattr(kitchen, "approval_status", "APPROVED" if kitchen.is_approved else "PENDING_APPROVAL"),
        "rating": kitchen.rating,
        "rating_count": kitchen.rating_count,
        "updated_at": kitchen.updated_at,
    }


# ── Notifications ─────────────────────────────────────────────────────────────
@router.get("/notifications", response_model=List[NotificationResponse])
def get_kitchen_notifications(
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(require_kitchen_owner),
    db: Session = Depends(get_db),
):
    """Retrieve operational notifications for this kitchen."""
    return KitchenService.get_notifications(db, current_user, limit=limit)


@router.put("/notifications/read-all")
@router.patch("/notifications/read-all")
def mark_all_kitchen_notifications_read(
    current_user: User = Depends(require_kitchen_owner),
    db: Session = Depends(get_db),
):
    """Mark all unread kitchen notifications as read."""
    count = KitchenService.mark_all_notifications_read(db, current_user)
    return {"status": "success", "marked_read_count": count}


@router.put("/notifications/{notification_id}/read")
@router.patch("/notifications/{notification_id}/read")
def mark_kitchen_notification_read(
    notification_id: str,
    current_user: User = Depends(require_kitchen_owner),
    db: Session = Depends(get_db),
):
    """Mark a specific kitchen notification as read."""
    KitchenService.mark_notification_read(db, current_user, notification_id)
    return {"status": "success"}


# ── Serialization Helpers ─────────────────────────────────────────────────────
def _serialize_kitchen_order(order) -> dict:
    addr_str = getattr(order, "delivery_address_text", None)
    if not addr_str and order.delivery_address:
        addr_str = f"{order.delivery_address.address_line1}, {order.delivery_address.city}, {getattr(order.delivery_address, 'state', '')} {order.delivery_address.postal_code}".strip()
    addr_dict = None
    if order.delivery_address:
        addr_dict = {
            "id": order.delivery_address.id,
            "address_line1": order.delivery_address.address_line1,
            "address_line2": order.delivery_address.address_line2,
            "city": order.delivery_address.city,
            "state": getattr(order.delivery_address, "state", ""),
            "postal_code": order.delivery_address.postal_code,
            "landmark": order.delivery_address.landmark,
            "latitude": getattr(order.delivery_address, "latitude", None),
            "longitude": getattr(order.delivery_address, "longitude", None),
            "is_default": order.delivery_address.is_default,
        }

    items_list = []
    for it in order.items:
        items_list.append({
            "id": it.id,
            "menu_item_id": it.menu_item_id,
            "item_name": it.item_name,
            "unit_price": it.unit_price,
            "quantity": it.quantity,
            "subtotal": it.subtotal,
            "total_price": it.subtotal,
            "special_requests": it.special_requests,
        })

    k_lat = getattr(order.kitchen, "latitude", None) if order.kitchen else None
    k_lng = getattr(order.kitchen, "longitude", None) if order.kitchen else None
    k_addr = getattr(order.kitchen, "address", None) if order.kitchen else None

    d_lat = getattr(order, "delivery_latitude", None)
    if d_lat is None and order.delivery_address:
        d_lat = getattr(order.delivery_address, "latitude", None)

    d_lng = getattr(order, "delivery_longitude", None)
    if d_lng is None and order.delivery_address:
        d_lng = getattr(order.delivery_address, "longitude", None)

    return {
        "id": order.id,
        "order_number": order.order_number,
        "customer_id": order.customer_id,
        "customer_name": order.customer.full_name if order.customer else None,
        "customer_phone": order.customer.phone_number if order.customer else None,
        "status": order.status,
        "subtotal": order.subtotal,
        "tax": order.tax,
        "delivery_fee": order.delivery_fee,
        "total_amount": order.total_amount,
        "payment_status": order.payment_status,
        "special_instructions": order.special_instructions,
        "rejection_reason": order.rejection_reason,
        "cancellation_reason": order.cancellation_reason,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "items": items_list,
        "delivery_address": addr_dict,
        "delivery_address_text": addr_str or "Standard Delivery",
        "delivery_latitude": d_lat,
        "delivery_longitude": d_lng,
        "kitchen_latitude": k_lat,
        "kitchen_longitude": k_lng,
        "kitchen_address": k_addr,
    }


def _serialize_menu_item_with_recipe(item) -> dict:
    recipe_ingredients = []
    for link in item.ingredients_recipe:
        recipe_ingredients.append({
            "ingredient_id": link.ingredient_id,
            "ingredient_name": link.ingredient.name if link.ingredient else "Unknown",
            "unit": link.ingredient.unit if link.ingredient else "",
            "quantity_required": link.quantity_required,
        })
    return {
        "id": item.id,
        "kitchen_id": item.kitchen_id,
        "meal_id": item.meal_id,
        "name": item.name,
        "description": item.description,
        "category": item.category,
        "cuisine": item.cuisine,
        "price": item.price,
        "is_available": item.is_available,
        "is_veg": item.is_veg,
        "image_url": item.display_image_url if hasattr(item, "display_image_url") and item.display_image_url else item.image_url,
        "image_source": getattr(item, "image_source", None) or "MANUAL",
        "manual_image_url": getattr(item, "manual_image_url", None),
        "created_at": item.created_at,
        "recipe_ingredients": recipe_ingredients,
    }


def _serialize_transaction(t) -> dict:
    return {
        "id": t.id,
        "kitchen_id": t.kitchen_id,
        "ingredient_id": t.ingredient_id,
        "ingredient_name": t.ingredient.name if t.ingredient else None,
        "transaction_type": t.transaction_type,
        "quantity": t.quantity,
        "balance_after": t.balance_after,
        "reference_order_id": t.reference_order_id,
        "reason": t.reason,
        "created_at": t.created_at,
    }


def _serialize_waste(w) -> dict:
    cost_val = getattr(w, "estimated_cost", None)
    cost_avail = False
    if cost_val is not None and cost_val > 0.0:
        cost_avail = True
    elif cost_val is not None and cost_val == 0.0:
        if hasattr(w, "ingredient") and w.ingredient and hasattr(w.ingredient, "purchases"):
            valid_p = [p for p in w.ingredient.purchases if p.unit_cost and p.unit_cost > 0.0]
            if valid_p:
                total_c = sum(float(p.total_cost if p.total_cost and p.total_cost > 0 else p.unit_cost * p.quantity) for p in valid_p)
                total_q = sum(float(p.quantity) for p in valid_p)
                avg_cost = total_c / total_q if total_q > 0 else 0.0
                if avg_cost > 0:
                    cost_val = round(w.quantity * avg_cost, 2)
                    cost_avail = True
                else:
                    cost_val = None
                    cost_avail = False
            else:
                cost_val = None
                cost_avail = False
        else:
            cost_val = None
            cost_avail = False
    else:
        cost_val = None
        cost_avail = False

    return {
        "id": w.id,
        "kitchen_id": w.kitchen_id,
        "ingredient_id": w.ingredient_id,
        "ingredient_name": w.ingredient.name if w.ingredient else None,
        "order_id": getattr(w, "order_id", None),
        "menu_item_id": getattr(w, "menu_item_id", None),
        "menu_item_name": getattr(w, "menu_item_name", None),
        "portions_wasted": getattr(w, "portions_wasted", None),
        "quantity": w.quantity,
        "unit": w.unit,
        "reason": w.reason,
        "recorded_by": w.recorded_by,
        "estimated_cost": cost_val,
        "cost_available": cost_avail,
        "source_event": getattr(w, "source_event", "MANUAL") or "MANUAL",
        "created_at": w.created_at,
    }


# ── FSSAI Food License Endpoints ──────────────────────────────────────────────
@router.post("/license/ocr-scan", response_model=LicenseOcrScanResponse)
async def scan_license_document(
    request: Request,
    file: Optional[UploadFile] = File(None),
    document: Optional[UploadFile] = File(None),
    current_user: User = Depends(require_kitchen_owner),
    db: Session = Depends(get_db),
):
    """
    Upload and inspect an FSSAI Food License document (PDF/JPG/PNG).
    Runs automated OCR extraction for owner review.
    Does NOT finalize the license or assume authenticity.
    """
    upload_file = file or document
    if not upload_file:
        try:
            form = await request.form()
            upload_file = form.get("file") or form.get("document")
        except Exception:
            pass

    if not upload_file or not hasattr(upload_file, "read"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A valid license document (PDF/JPG/PNG) is required.")

    file_bytes = await upload_file.read()
    orig_name = getattr(upload_file, "filename", None) or "license.pdf"
    content_type = getattr(upload_file, "content_type", None)
    file_meta = FssaiService.save_secure_license_file(file_bytes, orig_name, content_type)
    ocr_res = FssaiService.extract_ocr_data(file_bytes, orig_name)

    return LicenseOcrScanResponse(
        extracted_license_number=ocr_res.get("extracted_license_number"),
        extracted_business_name=ocr_res.get("extracted_business_name"),
        extracted_expiry_date=ocr_res.get("extracted_expiry_date"),
        extracted_issue_date=ocr_res.get("extracted_issue_date"),
        is_demo_document=ocr_res.get("is_demo_document", False),
        confidence=ocr_res.get("confidence", 0.0),
        ocr_status=ocr_res.get("ocr_status", "MANUAL_REQUIRED"),
        raw_text_snippet=ocr_res.get("raw_text_snippet"),
        notice=ocr_res.get("notice"),
        file_token=file_meta["filename"],
        original_filename=orig_name,
    )


@router.get("/license", response_model=Optional[KitchenLicenseResponse])
def get_kitchen_license(
    current_user: User = Depends(require_kitchen_owner),
    db: Session = Depends(get_db),
):
    """Retrieve the current kitchen owner's FSSAI Food License and document history."""
    kitchen = KitchenService._get_kitchen_profile(db, current_user, require_approved=False)
    if not kitchen.license:
        return None

    FssaiService.sync_license_expiration(db, kitchen.license)
    exp_dt = kitchen.license.expiry_date
    if exp_dt and hasattr(exp_dt, "tzinfo") and exp_dt.tzinfo is None:
        exp_dt = exp_dt.replace(tzinfo=timezone.utc)
    from datetime import timezone as dt_tz
    is_exp = kitchen.license.status == LicenseStatus.EXPIRED or (exp_dt is not None and exp_dt < utc_now())
    return KitchenLicenseResponse(
        id=kitchen.license.id,
        kitchen_id=kitchen.id,
        license_number=kitchen.license.license_number,
        raw_license_number=kitchen.license.raw_license_number,
        business_name=kitchen.license.business_name,
        issue_date=kitchen.license.issue_date,
        expiry_date=kitchen.license.expiry_date,
        status=kitchen.license.status,
        verification_source=kitchen.license.verification_source,
        verified_by_user_id=kitchen.license.verified_by_user_id,
        verified_at=kitchen.license.verified_at,
        correction_reason=kitchen.license.correction_reason,
        rejection_reason=kitchen.license.rejection_reason,
        duplicate_flag=kitchen.license.duplicate_flag,
        duplicate_details=kitchen.license.duplicate_details,
        ocr_extracted_data=kitchen.license.ocr_extracted_data,
        created_at=kitchen.license.created_at,
        updated_at=kitchen.license.updated_at,
        is_expired=is_exp,
        documents=[
            KitchenLicenseDocumentResponse(
                id=doc.id,
                original_filename=doc.original_filename,
                file_size=doc.file_size,
                mime_type=doc.mime_type,
                document_type=doc.document_type,
                is_active=doc.is_active,
                created_at=doc.created_at,
            )
            for doc in kitchen.license.documents
        ]
    )


@router.post("/license/submit", response_model=Optional[KitchenLicenseResponse])
async def submit_or_correct_license(
    request: Request,
    current_user: User = Depends(require_kitchen_owner),
    db: Session = Depends(get_db),
):
    """
    Submit reviewed & corrected FSSAI License data.
    Supports multipart/form-data with file upload or JSON with base64 / file_token.
    """
    kitchen = KitchenService._get_kitchen_profile(db, current_user, require_approved=False)
    content_type = request.headers.get("content-type", "")

    lic_num = None
    b_name = None
    exp_str = None
    iss_str = None
    ftoken = None
    fbytes = None
    fname = "license.pdf"
    fmime = "application/pdf"

    if "multipart/form-data" in content_type:
        form = await request.form()
        lic_num = form.get("license_number")
        b_name = form.get("business_name")
        exp_str = form.get("expiry_date")
        iss_str = form.get("issue_date")
        ftoken = form.get("file_token")
        upload_file = form.get("file") or form.get("document")
        if upload_file and hasattr(upload_file, "read"):
            fbytes = await upload_file.read()
            fname = getattr(upload_file, "filename", None) or "license.pdf"
            fmime = getattr(upload_file, "content_type", None) or "application/pdf"
    else:
        try:
            body = await request.json()
        except Exception:
            body = {}
        lic_num = body.get("license_number")
        b_name = body.get("business_name")
        exp_str = body.get("expiry_date")
        iss_str = body.get("issue_date")
        ftoken = body.get("file_token")
        doc_b64 = body.get("document_base64")
        if doc_b64:
            import base64
            if "," in doc_b64:
                header, doc_b64 = doc_b64.split(",", 1)
                if "pdf" in header:
                    fmime = "application/pdf"
                elif "png" in header:
                    fmime = "image/png"
                else:
                    fmime = "image/jpeg"
            fbytes = base64.b64decode(doc_b64)
            fname = body.get("filename") or "license.pdf"

    if not lic_num or not b_name or not exp_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="License number, business name, and expiry date are required."
        )

    exp_dt = FssaiService.parse_date(exp_str)
    if not exp_dt:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid expiry date format. Use YYYY-MM-DD.")
    iss_dt = FssaiService.parse_date(iss_str) if iss_str else None

    # Handle file
    file_meta = None
    if fbytes:
        file_meta = FssaiService.save_secure_license_file(fbytes, fname, fmime)
    elif ftoken:
        target_path = os.path.join(SECURE_LICENSES_DIR, os.path.basename(ftoken))
        if os.path.exists(target_path):
            ext = os.path.splitext(target_path)[1].lower()
            mime = "application/pdf" if ext == ".pdf" else ("image/png" if ext == ".png" else "image/jpeg")
            with open(target_path, "rb") as f:
                raw_bytes = f.read()
            file_meta = {
                "file_path": target_path,
                "filename": os.path.basename(target_path),
                "original_filename": os.path.basename(target_path),
                "file_size": len(raw_bytes),
                "mime_type": mime,
                "file_hash": hashlib.sha256(raw_bytes).hexdigest(),
            }

    if not file_meta:
        # Check if kitchen already has an active document
        if kitchen.license and kitchen.license.documents:
            active_doc = [d for d in kitchen.license.documents if d.is_active]
            doc_to_use = active_doc[0] if active_doc else kitchen.license.documents[0]
            file_meta = {
                "file_path": doc_to_use.file_path,
                "filename": os.path.basename(doc_to_use.file_path),
                "original_filename": doc_to_use.original_filename,
                "file_size": doc_to_use.file_size,
                "mime_type": doc_to_use.mime_type,
                "file_hash": doc_to_use.file_hash,
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A valid license document (PDF/JPG/PNG) must be uploaded."
            )

    doc_type = "REPLACEMENT" if (kitchen.license and kitchen.license.documents) else "INITIAL"
    lic_obj = FssaiService.create_or_update_license(
        db=db,
        kitchen_id=kitchen.id,
        license_number=lic_num,
        business_name=b_name,
        expiry_date=exp_dt,
        issue_date=iss_dt,
        file_meta=file_meta,
        document_type=doc_type,
        allow_test_identifiers=True,
    )
    kitchen.approval_status = "PENDING_APPROVAL"
    kitchen.is_approved = False
    db.commit()
    db.refresh(lic_obj)

    return get_kitchen_license(current_user=current_user, db=db)


@router.post("/license/renew", response_model=Optional[KitchenLicenseResponse])
async def renew_kitchen_license(
    request: Request,
    current_user: User = Depends(require_kitchen_owner),
    db: Session = Depends(get_db),
):
    """
    Upload renewed license document, extending validity while preserving document history.
    Supports both multipart/form-data and JSON payloads.
    """
    kitchen = KitchenService._get_kitchen_profile(db, current_user, require_approved=False)
    content_type = request.headers.get("content-type", "")

    lic_num = None
    b_name = None
    exp_str = None
    iss_str = None
    fbytes = None
    fname = "renewed_license.pdf"
    fmime = "application/pdf"

    if "multipart/form-data" in content_type:
        form = await request.form()
        lic_num = form.get("license_number")
        b_name = form.get("business_name")
        exp_str = form.get("expiry_date")
        iss_str = form.get("issue_date")
        upload_file = form.get("file") or form.get("document")
        if upload_file and hasattr(upload_file, "read"):
            fbytes = await upload_file.read()
            fname = getattr(upload_file, "filename", None) or "renewed_license.pdf"
            fmime = getattr(upload_file, "content_type", None) or "application/pdf"
    else:
        try:
            body = await request.json()
        except Exception:
            body = {}
        lic_num = body.get("license_number")
        b_name = body.get("business_name")
        exp_str = body.get("expiry_date")
        iss_str = body.get("issue_date")
        doc_b64 = body.get("document_base64")
        if doc_b64:
            import base64
            if "," in doc_b64:
                header, doc_b64 = doc_b64.split(",", 1)
                if "pdf" in header:
                    fmime = "application/pdf"
                elif "png" in header:
                    fmime = "image/png"
                else:
                    fmime = "image/jpeg"
            fbytes = base64.b64decode(doc_b64)
            fname = body.get("filename") or "renewed_license.pdf"

    if not lic_num or not b_name or not exp_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="License number, business name, and expiry date are required."
        )

    if not fbytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A new license certificate document file is required for renewal."
        )

    exp_dt = FssaiService.parse_date(exp_str)
    if not exp_dt:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid expiry date format. Use YYYY-MM-DD.")
    iss_dt = FssaiService.parse_date(iss_str) if iss_str else None

    file_meta = FssaiService.save_secure_license_file(fbytes, fname, fmime)
    ocr_meta = FssaiService.extract_ocr_data(fbytes, fname)

    lic_obj = FssaiService.create_or_update_license(
        db=db,
        kitchen_id=kitchen.id,
        license_number=lic_num,
        business_name=b_name,
        expiry_date=exp_dt,
        issue_date=iss_dt,
        file_meta=file_meta,
        ocr_meta=ocr_meta,
        document_type="RENEWAL",
        allow_test_identifiers=True,
    )

    kitchen.approval_status = "PENDING_APPROVAL"
    kitchen.is_approved = False
    db.commit()
    return get_kitchen_license(current_user=current_user, db=db)


@router.get("/license/document/{doc_id}")
def stream_kitchen_license_document(
    doc_id: str,
    current_user: User = Depends(require_kitchen_or_admin),
    db: Session = Depends(get_db),
):
    """
    Secure authenticated viewing of license document for the kitchen owner or platform administrators.
    Verifies that the document belongs to the requesting owner, unless user is an admin.
    """
    doc = db.query(KitchenLicenseDocument).filter(KitchenLicenseDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    if current_user.role != UserRole.ADMIN:
        kitchen = KitchenService._get_kitchen_profile(db, current_user, require_approved=False)
        if not kitchen.license or doc.license_id != kitchen.license.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access forbidden: Document belongs to another kitchen.")

    if not os.path.exists(doc.file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document file missing on disk.")

    return FileResponse(
        path=doc.file_path,
        media_type=doc.mime_type,
        filename=doc.original_filename,
    )
