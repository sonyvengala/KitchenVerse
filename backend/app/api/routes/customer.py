"""
Customer Portal API Endpoints.
Guarded by require_customer RBAC dependency.
"""
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from backend.app.core.database import get_db
from backend.app.core.deps import require_customer, get_current_user
from backend.app.models.user import User, Address, CustomerProfile
from backend.app.models.platform import Notification
from backend.app.models.order import Favorite, Order
from backend.app.models.enums import OrderStatus
from backend.app.schemas.customer import (
    KitchenPublic,
    KitchenDetailResponse,
    MenuItemPublic,
    CheckoutPreviewRequest,
    CheckoutPreviewResponse,
    OrderCreateRequest,
    OrderDetailResponse,
    FavoriteToggleRequest,
    ReviewCreateRequest,
    NotificationResponse,
    AddressCreate,
    AddressUpdate,
    AddressResponse,
    CustomerProfileUpdate,
    PromotionPublic,
    UpdateDeliveryLocationRequest,
    CancellationRequestCreate,
    CancellationRequestResponse,
)
from backend.app.services.customer_service import CustomerService

router = APIRouter(prefix="/customer", tags=["Customer Portal"])


# 1. Kitchens & Menu Browsing (Public / Authenticated Customer)
@router.get("/kitchens", response_model=List[KitchenPublic])
def list_kitchens(
    query: Optional[str] = Query(None, description="Search kitchen name or description"),
    city: Optional[str] = Query(None, description="Filter by city"),
    cuisine: Optional[str] = Query(None, description="Filter by cuisine"),
    latitude: Optional[float] = Query(None, ge=-90.0, le=90.0, description="Customer latitude for nearby distance discovery"),
    longitude: Optional[float] = Query(None, ge=-180.0, le=180.0, description="Customer longitude for nearby distance discovery"),
    radius_km: Optional[float] = Query(None, ge=0.5, le=100.0, description="Discovery radius in kilometers"),
    db: Session = Depends(get_db)
):
    """Browse open and approved cloud kitchens with optional real geolocation discovery."""
    return CustomerService.get_kitchens(
        db,
        query=query,
        city=city,
        cuisine=cuisine,
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
    )


# 1b. Real Food-Delivery Style Location Discovery & Autocomplete
@router.get("/locations/autocomplete")
def autocomplete_locations(
    q: str = Query(..., min_length=2, description="Search query for address or landmark"),
    latitude: Optional[float] = Query(None, description="Optional customer latitude for local bias"),
    longitude: Optional[float] = Query(None, description="Optional customer longitude for local bias"),
):
    """
    Real food-delivery-style autocomplete location search.
    Provides structured suggestions with main_text, secondary_text, formatted_address, latitude, longitude.
    """
    return CustomerService.autocomplete_locations(q, latitude=latitude, longitude=longitude)


@router.get("/locations/reverse-geocode")
def reverse_geocode(
    lat: float = Query(..., ge=-90.0, le=90.0),
    lng: float = Query(..., ge=-180.0, le=180.0),
):
    """
    Reverse geocode real coordinates into structured address and city name.
    """
    return CustomerService.reverse_geocode(lat, lng)


@router.get("/kitchens/{kitchen_id}", response_model=KitchenDetailResponse)
def get_kitchen_detail(
    kitchen_id: str,
    db: Session = Depends(get_db)
):
    """Retrieve full details of a kitchen and its available menu items."""
    kitchen = CustomerService.get_kitchen_detail(db, kitchen_id)
    return {
        "id": kitchen.id,
        "kitchen_name": kitchen.kitchen_name,
        "center_id": kitchen.center_id,
        "description": kitchen.description,
        "address": kitchen.address,
        "city": kitchen.city,
        "phone": kitchen.phone,
        "postal_code": getattr(kitchen, "postal_code", None),
        "operating_hours": getattr(kitchen, "operating_hours", None),
        "latitude": getattr(kitchen, "latitude", None),
        "longitude": getattr(kitchen, "longitude", None),
        "cuisine": getattr(kitchen, "cuisine", None),
        "is_open": kitchen.is_open,
        "rating": kitchen.rating,
        "rating_count": kitchen.rating_count,
        "menu_items": [item for item in kitchen.menu_items if item.is_available]
    }


@router.get("/menu", response_model=List[MenuItemPublic])
def list_menu_items(
    query: Optional[str] = Query(None, description="Search dish name or description"),
    category: Optional[str] = Query(None, description="Filter by category (Beverages, Rice Bowl, etc.)"),
    cuisine: Optional[str] = Query(None, description="Filter by cuisine (Indian, Italian, Thai, etc.)"),
    is_veg: Optional[bool] = Query(None, description="Vegetarian filter"),
    max_price: Optional[float] = Query(None, description="Maximum price filter"),
    db: Session = Depends(get_db)
):
    """Search and browse dishes across all approved cloud kitchens."""
    return CustomerService.get_menu_items(
        db, query=query, category=category, cuisine=cuisine, is_veg=is_veg, max_price=max_price
    )


# 2. Checkout & Orders (Requires CUSTOMER role)
@router.post("/checkout/preview", response_model=CheckoutPreviewResponse)
def checkout_preview(
    req: CheckoutPreviewRequest,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    """Calculate cart totals, taxes, and fees server-side based on verified database prices."""
    return CustomerService.calculate_checkout_preview(db, req, current_user)


def _serialize_customer_order(order) -> dict:
    allowed_cancel = order.status in [
        OrderStatus.ORDER_PLACED,
        OrderStatus.PAYMENT_CONFIRMED,
        OrderStatus.KITCHEN_ACCEPTED,
        OrderStatus.PREPARING,
    ]
    warning = (
        "Your food is already being prepared. Cancelling this order may result in food wastage."
        if order.status == OrderStatus.PREPARING
        else None
    )

    addr_text = order.delivery_address_text
    addr_lat = order.delivery_latitude
    addr_lon = order.delivery_longitude
    if not addr_text and order.delivery_address:
        parts = [order.delivery_address.address_line1]
        if order.delivery_address.address_line2:
            parts.append(order.delivery_address.address_line2)
        if getattr(order.delivery_address, "landmark", None):
            parts.append(f"Near {order.delivery_address.landmark}")
        parts.append(order.delivery_address.city)
        if getattr(order.delivery_address, "state", None):
            parts.append(order.delivery_address.state)
        if order.delivery_address.postal_code:
            parts.append(order.delivery_address.postal_code)
        addr_text = ", ".join(p for p in parts if p)
    if addr_lat is None and order.delivery_address:
        addr_lat = order.delivery_address.latitude
    if addr_lon is None and order.delivery_address:
        addr_lon = order.delivery_address.longitude

    latest_cr = None
    if getattr(order, "cancellation_requests", None):
        sorted_crs = sorted(order.cancellation_requests, key=lambda c: c.created_at, reverse=True)
        if sorted_crs:
            latest_cr = sorted_crs[0]

    return {
        "id": order.id,
        "order_number": order.order_number,
        "kitchen_id": order.kitchen_id,
        "kitchen_name": order.kitchen.kitchen_name if order.kitchen else None,
        "status": order.status,
        "subtotal": order.subtotal,
        "discount_amount": getattr(order, "discount_amount", 0.0),
        "promotion_code": getattr(order, "promotion_code", None),
        "tax": order.tax,
        "delivery_fee": order.delivery_fee,
        "total_amount": order.total_amount,
        "payment_status": order.payment_status,
        "special_instructions": order.special_instructions,
        "rejection_reason": order.rejection_reason,
        "cancellation_reason": order.cancellation_reason,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "items": order.items,
        "delivery_address": order.delivery_address,
        "delivery_address_text": addr_text or "Standard Delivery",
        "delivery_latitude": addr_lat,
        "delivery_longitude": addr_lon,
        "delivery_distance_km": getattr(order, "delivery_distance_km", None),
        "pricing_breakdown_json": getattr(order, "pricing_breakdown_json", None),
        "pricing_breakdown": json.loads(order.pricing_breakdown_json) if getattr(order, "pricing_breakdown_json", None) else None,
        "can_cancel": allowed_cancel,
        "cancellation_warning": warning,
        "cancellation_request": {
            "id": latest_cr.id,
            "order_id": latest_cr.order_id,
            "customer_id": latest_cr.customer_id,
            "kitchen_id": latest_cr.kitchen_id,
            "reason": latest_cr.reason,
            "customer_note": getattr(latest_cr, "customer_note", None),
            "status": latest_cr.status,
            "admin_id": latest_cr.admin_id,
            "reviewed_by": latest_cr.admin_id,
            "admin_note": latest_cr.admin_note,
            "created_at": latest_cr.created_at,
            "requested_at": latest_cr.created_at,
            "resolved_at": latest_cr.resolved_at,
            "reviewed_at": latest_cr.resolved_at,
        } if latest_cr else None,
    }


@router.post("/orders", response_model=OrderDetailResponse, status_code=status.HTTP_201_CREATED)
def place_order(
    req: OrderCreateRequest,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    """Place a new order with verified items, server-calculated totals, and notification dispatch."""
    order = CustomerService.place_order(db, current_user, req)
    return _serialize_customer_order(order)


@router.get("/orders", response_model=List[OrderDetailResponse])
def get_orders(
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    """Retrieve customer's order history."""
    orders = CustomerService.get_customer_orders(db, current_user.id)
    return [_serialize_customer_order(o) for o in orders]


@router.get("/orders/{order_id}", response_model=OrderDetailResponse)
def get_order_tracking(
    order_id: str,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    """Track a specific order in real time."""
    order = CustomerService.get_order_tracking(db, current_user.id, order_id)
    return _serialize_customer_order(order)


@router.post("/orders/{order_id}/cancel", response_model=OrderDetailResponse)
def cancel_order(
    order_id: str,
    reason: Optional[str] = Query(None),
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    """Cancel order with food preparation lifecycle enforcement."""
    order = CustomerService.cancel_order(db, current_user.id, order_id, reason)
    return _serialize_customer_order(order)


@router.post("/orders/{order_id}/cancellation-request", response_model=CancellationRequestResponse)
@router.post("/orders/{order_id}/request-cancellation", response_model=CancellationRequestResponse)
def request_order_cancellation(
    order_id: str,
    req: CancellationRequestCreate,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    """
    Customer requests cancellation of a READY order.
    Direct cancellation is blocked for READY orders — this creates
    a CancellationRequest for Admin review.
    """
    cr = CustomerService.submit_cancellation_request(
        db, current_user.id, order_id, reason=req.reason, customer_note=req.customer_note
    )
    return cr


@router.get("/orders/{order_id}/cancellation-request", response_model=Optional[CancellationRequestResponse])
def get_cancellation_request(
    order_id: str,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    """Get the latest cancellation request status for an order (customer view)."""
    cr = CustomerService.get_cancellation_request_for_order(db, current_user.id, order_id)
    if not cr:
        return None
    return cr


@router.put("/orders/{order_id}/delivery-location", response_model=OrderDetailResponse)
def update_order_delivery_location(
    order_id: str,
    req: UpdateDeliveryLocationRequest,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    """Update or confirm delivery coordinates for an active order."""
    order = CustomerService.update_order_delivery_location(db, current_user, order_id, req)
    return _serialize_customer_order(order)


@router.post("/orders/{order_id}/review")
def review_order(
    order_id: str,
    req: ReviewCreateRequest,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    """Submit a review for a delivered order."""
    req.order_id = order_id
    review = CustomerService.create_review(db, current_user.id, req)
    return {"message": "Review submitted successfully", "review_id": review.id}


# 3. Favorites
@router.post("/favorites/toggle")
def toggle_favorite(
    req: FavoriteToggleRequest,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    """Toggle a kitchen or menu item favorite."""
    is_favorited = CustomerService.toggle_favorite(
        db, current_user.id, kitchen_id=req.kitchen_id, menu_item_id=req.menu_item_id
    )
    return {"is_favorite": is_favorited}


@router.get("/favorites")
def get_favorites(
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    """Retrieve customer's favorite kitchens and dishes."""
    favs = db.query(Favorite).filter(Favorite.customer_id == current_user.id).all()
    kitchens = []
    dishes = []
    for f in favs:
        if f.kitchen:
            kitchens.append({
                "id": f.kitchen.id,
                "kitchen_name": f.kitchen.kitchen_name,
                "city": f.kitchen.city,
                "rating": f.kitchen.rating,
                "is_open": f.kitchen.is_open
            })
        if f.menu_item:
            dishes.append({
                "id": f.menu_item.id,
                "name": f.menu_item.name,
                "category": f.menu_item.category,
                "price": f.menu_item.price,
                "is_veg": f.menu_item.is_veg,
                "kitchen_name": f.menu_item.kitchen.kitchen_name if f.menu_item.kitchen else None
            })
    return {"kitchens": kitchens, "dishes": dishes}


# 4. Notifications
@router.get("/notifications", response_model=List[NotificationResponse])
def get_notifications(
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    """Retrieve customer notifications."""
    return db.query(Notification).filter(
        Notification.user_id == current_user.id
    ).order_by(desc(Notification.created_at)).limit(50).all()


@router.put("/notifications/{notification_id}/read")
@router.patch("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    """Mark a notification as read."""
    notif = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id
    ).first()
    if notif:
        notif.is_read = True
        db.commit()
    return {"status": "success"}


@router.put("/notifications/read-all")
@router.patch("/notifications/read-all")
def mark_all_notifications_read(
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    """Mark all customer notifications as read."""
    count = CustomerService.mark_all_notifications_read(db, current_user.id)
    return {"status": "success", "marked_read_count": count}


# 5. Promotions
@router.get("/promotions", response_model=List[PromotionPublic])
def list_active_promotions(
    db: Session = Depends(get_db)
):
    """List all currently active promotional codes available for checkout discounts."""
    return CustomerService.get_active_promotions(db)


# 6. Addresses & Profile
@router.get("/addresses", response_model=List[AddressResponse])
def get_addresses(
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    """Get customer's saved delivery addresses."""
    return db.query(Address).filter(Address.user_id == current_user.id).order_by(Address.is_default.desc(), Address.created_at.desc()).all()


@router.post("/addresses", response_model=AddressResponse, status_code=status.HTTP_201_CREATED)
def create_address(
    req: AddressCreate,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    """Add a new delivery address with optional geo-coordinates, label, and instructions."""
    existing_count = db.query(Address).filter(Address.user_id == current_user.id).count()
    is_default = req.is_default or existing_count == 0

    if is_default:
        # unset previous default
        db.query(Address).filter(Address.user_id == current_user.id).update({"is_default": False})

    addr = Address(
        user_id=current_user.id,
        address_line1=req.address_line1,
        address_line2=req.address_line2,
        city=req.city,
        state=req.state,
        postal_code=req.postal_code,
        landmark=req.landmark,
        latitude=req.latitude,
        longitude=req.longitude,
        label=req.label or "Home",
        delivery_instructions=req.delivery_instructions,
        is_default=is_default
    )
    db.add(addr)
    db.commit()
    db.refresh(addr)
    return addr


@router.put("/addresses/{address_id}", response_model=AddressResponse)
def update_address(
    address_id: str,
    req: AddressUpdate,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    """Update an existing customer address."""
    addr = db.query(Address).filter(Address.id == address_id).first()
    if not addr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found.")
    if addr.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to update an address owned by another customer."
        )

    if req.is_default:
        db.query(Address).filter(Address.user_id == current_user.id).update({"is_default": False})

    if req.address_line1 is not None:
        addr.address_line1 = req.address_line1
    if req.address_line2 is not None:
        addr.address_line2 = req.address_line2
    if req.city is not None:
        addr.city = req.city
    if req.state is not None:
        addr.state = req.state
    if req.postal_code is not None:
        addr.postal_code = req.postal_code
    if req.landmark is not None:
        addr.landmark = req.landmark
    if req.latitude is not None:
        addr.latitude = req.latitude
    if req.longitude is not None:
        addr.longitude = req.longitude
    if req.label is not None:
        addr.label = req.label
    if req.delivery_instructions is not None:
        addr.delivery_instructions = req.delivery_instructions
    if req.is_default is not None:
        addr.is_default = req.is_default

    db.commit()
    db.refresh(addr)
    return addr


@router.delete("/addresses/{address_id}")
def delete_address(
    address_id: str,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    """
    Delete a customer address.
    Preserves historical order address records (snapshots, full formatted address text, and coordinates)
    so historical orders are never corrupted or altered.
    If the deleted address was the default, automatically selects another eligible saved address as default.
    """
    addr = db.query(Address).filter(Address.id == address_id).first()
    if not addr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found.")
    if addr.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to delete an address owned by another customer."
        )

    was_default = addr.is_default

    # 1. Preserve historical order records referencing this address
    referencing_orders = db.query(Order).filter(Order.delivery_address_id == addr.id).all()
    for order in referencing_orders:
        if not order.delivery_address_text:
            parts = [addr.address_line1]
            if addr.address_line2:
                parts.append(addr.address_line2)
            if addr.landmark:
                parts.append(f"Near {addr.landmark}")
            parts.append(addr.city)
            if addr.state:
                parts.append(addr.state)
            if addr.postal_code:
                parts.append(addr.postal_code)
            order.delivery_address_text = ", ".join(p for p in parts if p)

        if not order.delivery_address_snapshot:
            order.delivery_address_snapshot = json.dumps({
                "id": addr.id,
                "label": addr.label or "Home",
                "address_line1": addr.address_line1,
                "address_line2": addr.address_line2,
                "city": addr.city,
                "state": addr.state,
                "postal_code": addr.postal_code,
                "landmark": addr.landmark,
                "latitude": addr.latitude,
                "longitude": addr.longitude,
                "delivery_instructions": addr.delivery_instructions
            })
        if order.delivery_latitude is None and addr.latitude is not None:
            order.delivery_latitude = addr.latitude
        if order.delivery_longitude is None and addr.longitude is not None:
            order.delivery_longitude = addr.longitude

        # Safe disassociation: nullify FK reference while preserving complete snapshot & text
        order.delivery_address_id = None

    # 2. Remove address
    db.delete(addr)
    db.flush()

    # 3. If the deleted address was the default, automatically designate another remaining address
    new_default_id = None
    if was_default:
        remaining_addr = (
            db.query(Address)
            .filter(Address.user_id == current_user.id)
            .order_by(Address.created_at.desc())
            .first()
        )
        if remaining_addr:
            remaining_addr.is_default = True
            new_default_id = remaining_addr.id

    db.commit()
    return {
        "message": "Address deleted successfully",
        "deleted_address_id": address_id,
        "new_default_id": new_default_id
    }


@router.put("/addresses/{address_id}/default", response_model=AddressResponse)
def set_default_address(
    address_id: str,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    """Set an address as the default delivery address."""
    addr = db.query(Address).filter(Address.id == address_id).first()
    if not addr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found.")
    if addr.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to update an address owned by another customer."
        )

    db.query(Address).filter(Address.user_id == current_user.id).update({"is_default": False})
    addr.is_default = True
    db.commit()
    db.refresh(addr)
    return addr


@router.get("/profile")
def get_profile(
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    """Get customer profile details."""
    profile = db.query(CustomerProfile).filter(CustomerProfile.user_id == current_user.id).first()
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "phone_number": current_user.phone_number,
        "dietary_preferences": profile.dietary_preferences if profile else None,
        "addresses_count": len(current_user.addresses)
    }


@router.put("/profile")
def update_profile(
    req: CustomerProfileUpdate,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    """Update customer profile information."""
    if req.full_name is not None:
        current_user.full_name = req.full_name
    if req.phone_number is not None:
        current_user.phone_number = req.phone_number

    profile = db.query(CustomerProfile).filter(CustomerProfile.user_id == current_user.id).first()
    if profile and req.dietary_preferences is not None:
        profile.dietary_preferences = req.dietary_preferences

    db.commit()
    return {"message": "Profile updated successfully"}
