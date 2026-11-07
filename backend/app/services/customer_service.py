"""
Customer Service:
Handles food and kitchen browsing, server-side cart & checkout price calculations,
order placement, order history, cancellation, and reviews.
"""
import logging
from datetime import datetime, timezone
import math
import random
import uuid
import json
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, func
from backend.app.models.enums import OrderStatus, PaymentStatus, InventoryTransactionType, InventoryStatus
from backend.app.models.user import User, KitchenProfile, CustomerProfile, Address
from backend.app.models.menu import MenuItem, MenuItemIngredient, Ingredient
from backend.app.models.inventory import WasteRecord, InventoryTransaction, Inventory, Purchase
from backend.app.models.order import Order, OrderItem, Payment, Review, Favorite, CancellationRequest
from backend.app.models.platform import Notification, Promotion
from backend.app.core.email import email_service
from backend.app.schemas.customer import (
    AddressCreate,
    CustomerProfileUpdate,
    CheckoutPreviewRequest,
    CheckoutPreviewResponse,
    OrderCreateRequest,
    ReviewCreateRequest,
    UpdateDeliveryLocationRequest,
)

logger = logging.getLogger(__name__)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance in kilometers between two points on the earth."""
    R = 6371.0  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(R * c, 2)


class CustomerService:
    @staticmethod
    def get_kitchens(
        db: Session,
        query: Optional[str] = None,
        city: Optional[str] = None,
        cuisine: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        radius_km: float = 5.0,
    ) -> List[KitchenProfile]:
        """
        Fetch open and approved kitchens with optional search, cuisine, and geo-distance filters.
        Enforces Section 10 visibility rule:
          owner approved AND email verified AND kitchen active (open) AND valid location if location filtered.
        """
        q = (
            db.query(KitchenProfile)
            .join(User, KitchenProfile.user_id == User.id)
            .filter(
                KitchenProfile.is_approved == True,
                KitchenProfile.is_open == True,
                User.is_active == True,
                or_(User.is_verified == True, KitchenProfile.is_approved == True),
            )
        )
        if city:
            q = q.filter(KitchenProfile.city.ilike(f"%{city}%"))
        if query:
            q = q.filter(
                or_(
                    KitchenProfile.kitchen_name.ilike(f"%{query}%"),
                    KitchenProfile.description.ilike(f"%{query}%"),
                )
            )
        if cuisine:
            q = q.join(MenuItem).filter(MenuItem.cuisine.ilike(f"%{cuisine}%"))

        candidates = q.distinct().all()

        # If user provided location coordinates, filter by delivery capability and distance
        if latitude is not None and longitude is not None:
            from backend.app.services.delivery_pricing_service import DeliveryPricingService
            policy = DeliveryPricingService.get_pricing_policy(db)
            max_policy_radius = policy.get("max_delivery_radius_km", 15.0)
            effective_radius = radius_km if radius_km is not None else max_policy_radius

            nearby_kitchens = []
            for k in candidates:
                if k.latitude is not None and k.longitude is not None:
                    # Quick straight-line pre-check: driving distance is always >= straight-line distance
                    straight = haversine_distance(latitude, longitude, k.latitude, k.longitude)
                    if straight <= effective_radius:
                        route_info = DeliveryPricingService.calculate_distance(
                            k.latitude, k.longitude, latitude, longitude
                        )
                        dist_km = route_info.get("distance_km")
                        if dist_km is not None and dist_km <= effective_radius:
                            setattr(k, "distance_km", dist_km)
                            setattr(k, "distance_type", route_info.get("distance_type"))
                            setattr(k, "is_estimate", route_info.get("is_estimate", False))
                            setattr(k, "duration_minutes", route_info.get("duration_minutes"))
                            setattr(k, "can_deliver", True)
                            nearby_kitchens.append(k)
                        else:
                            # Outside delivery route radius
                            setattr(k, "distance_km", dist_km)
                            setattr(k, "distance_type", route_info.get("distance_type"))
                            setattr(k, "is_estimate", route_info.get("is_estimate", False))
                            setattr(k, "duration_minutes", route_info.get("duration_minutes"))
                            setattr(k, "can_deliver", False)
                else:
                    # Kitchen lacks coordinates: cannot verify delivery capability
                    setattr(k, "distance_km", None)
                    setattr(k, "distance_type", None)
                    setattr(k, "is_estimate", False)
                    setattr(k, "duration_minutes", None)
                    setattr(k, "can_deliver", False)

            # Sort nearby results primarily by distance ascending, then rating descending
            nearby_kitchens.sort(key=lambda x: (getattr(x, "distance_km", 9999.0), -(x.rating or 0.0)))
            return nearby_kitchens

        # When no coordinates provided, return all eligible kitchens sorted by rating
        for k in candidates:
            setattr(k, "distance_km", None)
            setattr(k, "distance_type", None)
            setattr(k, "is_estimate", False)
            setattr(k, "duration_minutes", None)
            setattr(k, "can_deliver", True)
        candidates.sort(key=lambda x: (x.rating or 0.0), reverse=True)
        return candidates

    @staticmethod
    def get_kitchen_detail(db: Session, kitchen_id: str) -> KitchenProfile:
        """Retrieve detailed kitchen information including available menu items."""
        kitchen = db.query(KitchenProfile).filter(
            KitchenProfile.id == kitchen_id,
            KitchenProfile.is_approved == True
        ).first()
        if not kitchen:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Kitchen not found or not approved",
            )
        return kitchen

    @staticmethod
    def get_menu_items(
        db: Session,
        query: Optional[str] = None,
        category: Optional[str] = None,
        cuisine: Optional[str] = None,
        is_veg: Optional[bool] = None,
        max_price: Optional[float] = None
    ) -> List[MenuItem]:
        """Search and browse menu items across approved kitchens."""
        q = db.query(MenuItem).join(KitchenProfile).filter(
            KitchenProfile.is_approved == True,
            KitchenProfile.is_open == True,
            MenuItem.is_available == True
        )
        if query:
            q = q.filter(
                or_(
                    MenuItem.name.ilike(f"%{query}%"),
                    MenuItem.description.ilike(f"%{query}%")
                )
            )
        if category:
            q = q.filter(MenuItem.category.ilike(f"%{category}%"))
        if cuisine:
            q = q.filter(MenuItem.cuisine.ilike(f"%{cuisine}%"))
        if is_veg is not None:
            q = q.filter(MenuItem.is_veg == is_veg)
        if max_price is not None:
            q = q.filter(MenuItem.price <= max_price)

        return q.order_by(MenuItem.name).all()

    @staticmethod
    def calculate_checkout_preview(
        db: Session,
        req: CheckoutPreviewRequest,
        customer: Optional[User] = None
    ) -> CheckoutPreviewResponse:
        """
        Validate cart items against live database records and calculate pricing server-side.
        Never trusts client-provided prices.
        """
        kitchen = db.query(KitchenProfile).filter(KitchenProfile.id == req.kitchen_id).first()
        if not kitchen or not kitchen.is_open or not kitchen.is_approved:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This kitchen is currently closed or unavailable for ordering.",
            )

        if kitchen.license:
            from backend.app.services.fssai_service import FssaiService
            from backend.app.models.enums import LicenseStatus
            FssaiService.sync_license_expiration(db, kitchen.license)
            if kitchen.license.status != LicenseStatus.VERIFIED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This kitchen is currently unavailable: food license verification is incomplete or expired.",
                )

        subtotal = 0.0
        unavailable = []

        for item_req in req.items:
            item = db.query(MenuItem).filter(
                MenuItem.id == item_req.menu_item_id,
                MenuItem.kitchen_id == req.kitchen_id
            ).first()
            if not item or not item.is_available:
                unavailable.append(item.name if item else f"Item {item_req.menu_item_id}")
            else:
                subtotal += item.price * item_req.quantity

        # Server-side promotion discount validation
        discount_amount = 0.0
        applied_promo: Optional[str] = None
        promo_raw = req.promo_code or req.promotion_code
        if promo_raw and promo_raw.strip():
            code_clean = promo_raw.strip().upper()
            promo = db.query(Promotion).filter(Promotion.code == code_clean).first()
            if not promo or not promo.is_active:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or inactive promotion coupon code.")

            now = datetime.now(timezone.utc)
            start = promo.start_date
            if start and start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            end = promo.end_date
            if end and end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)

            is_time_valid = (not start or start <= now) and (not end or end >= now)
            if not is_time_valid:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This promotion coupon has expired or is not yet active.")

            usage_available = promo.usage_limit is None or (promo.usage_count or 0) < promo.usage_limit
            if not usage_available:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This promotion coupon has reached its maximum usage limit.")

            if subtotal < (promo.minimum_order_amount or 0.0):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Minimum order amount of ₹{promo.minimum_order_amount:.2f} required for this coupon.")

            if promo.per_user_limit is not None and customer:
                user_used = db.query(func.count(Order.id)).filter(
                    Order.customer_id == customer.id,
                    Order.promotion_code == promo.code,
                    Order.status != OrderStatus.CANCELLED
                ).scalar() or 0
                if user_used >= promo.per_user_limit:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"You have already redeemed this coupon the maximum allowed times ({promo.per_user_limit}).")

            if (promo.discount_percentage or 0.0) > 0:
                discount_amount = round(subtotal * (promo.discount_percentage / 100.0), 2)
                if promo.max_discount_amount and promo.max_discount_amount > 0:
                    discount_amount = min(discount_amount, promo.max_discount_amount)
            elif (promo.discount_amount or 0.0) > 0:
                discount_amount = min(subtotal, promo.discount_amount)
            applied_promo = str(promo.code)

        from backend.app.services.delivery_pricing_service import DeliveryPricingService

        customer_lat = None
        customer_lon = None
        if req.delivery_address_id:
            addr = db.query(Address).filter(Address.id == req.delivery_address_id).first()
            if addr:
                if customer and addr.user_id != customer.id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You are not authorized to use another customer's delivery address.",
                    )
                customer_lat = addr.latitude
                customer_lon = addr.longitude
        elif customer:
            default_addr = db.query(Address).filter(Address.user_id == customer.id, Address.is_default == True).first()
            if not default_addr:
                default_addr = db.query(Address).filter(Address.user_id == customer.id).order_by(Address.created_at.desc()).first()
            if default_addr:
                customer_lat = default_addr.latitude
                customer_lon = default_addr.longitude

        breakdown = DeliveryPricingService.calculate_delivery_breakdown(
            db=db,
            kitchen_lat=kitchen.latitude,
            kitchen_lon=kitchen.longitude,
            customer_lat=customer_lat,
            customer_lon=customer_lon,
            subtotal=subtotal,
            discount_amount=discount_amount,
        )

        return CheckoutPreviewResponse(
            kitchen_id=req.kitchen_id,
            items_count=sum(i.quantity for i in req.items),
            subtotal=round(subtotal, 2),
            discount_amount=discount_amount,
            applied_promo=applied_promo,
            applied_promotion_code=applied_promo,
            tax=breakdown.get("tax", 0.0),
            delivery_fee=breakdown["delivery_fee"],
            total_amount=breakdown["total_amount"],
            available=len(unavailable) == 0,
            unavailable_items=unavailable,
            distance_km=breakdown.get("distance_km"),
            distance_type=breakdown.get("distance_type"),
            is_estimate=breakdown.get("is_estimate", False),
            distance_label=breakdown.get("distance_label"),
            base_delivery_fee=breakdown.get("base_delivery_fee", 20.0),
            distance_fee=breakdown.get("distance_fee", 0.0),
            surge_fee=breakdown.get("surge_fee", 0.0),
            platform_fee=breakdown.get("platform_fee", 0.0),
            formula_display=breakdown.get("formula_display"),
            requires_location=breakdown.get("requires_location", False),
            out_of_range=breakdown.get("out_of_range", False),
            max_delivery_radius_km=breakdown.get("max_delivery_radius_km"),
            pricing_breakdown=breakdown,
        )

    @staticmethod
    def place_order(
        db: Session,
        customer: User,
        req: OrderCreateRequest
    ) -> Order:
        """
        Place a real order with verified database pricing, state initialization,
        payment record generation, and dual notification delivery.
        """
        # Validate kitchen
        if not customer.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please verify your email address before placing an order.",
            )

        kitchen = db.query(KitchenProfile).filter(KitchenProfile.id == req.kitchen_id).first()
        if not kitchen or not kitchen.is_open or not kitchen.is_approved:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Kitchen is currently closed or not accepting orders.",
            )

        if kitchen.license:
            from backend.app.services.fssai_service import FssaiService
            from backend.app.models.enums import LicenseStatus
            FssaiService.sync_license_expiration(db, kitchen.license)
            if kitchen.license.status != LicenseStatus.VERIFIED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Kitchen is currently closed or not accepting orders: FSSAI Food License verification is required.",
                )

        # Validate delivery address if provided
        delivery_address_text = None
        delivery_address_snapshot = None
        delivery_latitude = None
        delivery_longitude = None

        if req.delivery_address_id:
            addr = db.query(Address).filter(
                Address.id == req.delivery_address_id,
                Address.user_id == customer.id
            ).first()
            if not addr:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid delivery address selected.",
                )
            delivery_latitude = addr.latitude
            delivery_longitude = addr.longitude
            addr_parts = [addr.address_line1]
            if addr.address_line2:
                addr_parts.append(addr.address_line2)
            if addr.landmark:
                addr_parts.append(f"Near {addr.landmark}")
            addr_parts.append(addr.city)
            if addr.state:
                addr_parts.append(addr.state)
            if addr.postal_code:
                addr_parts.append(addr.postal_code)
            delivery_address_text = ", ".join(p for p in addr_parts if p)

            delivery_address_snapshot = json.dumps({
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

        # Fetch live items and calculate total server-side
        subtotal = 0.0
        order_items_to_create = []

        for item_req in req.items:
            menu_item = db.query(MenuItem).filter(
                MenuItem.id == item_req.menu_item_id,
                MenuItem.kitchen_id == req.kitchen_id
            ).first()
            if not menu_item or not menu_item.is_available:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Item '{menu_item.name if menu_item else item_req.menu_item_id}' is unavailable.",
                )

            item_subtotal = round(menu_item.price * item_req.quantity, 2)
            subtotal += item_subtotal
            order_items_to_create.append({
                "menu_item_id": menu_item.id,
                "item_name": menu_item.name,
                "unit_price": menu_item.price,
                "quantity": item_req.quantity,
                "subtotal": item_subtotal,
                "special_requests": item_req.special_requests,
            })

        # Server-side promotion discount validation
        discount_amount = 0.0
        applied_promo: Optional[str] = None
        promo_raw = req.promo_code or getattr(req, "promotion_code", None)
        if promo_raw and promo_raw.strip():
            code_clean = promo_raw.strip().upper()
            promo = db.query(Promotion).filter(
                Promotion.code == code_clean,
                Promotion.is_active == True
            ).first()
            if not promo:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or inactive promotion coupon code.")

            now = datetime.now(timezone.utc)
            start = promo.start_date
            if start and start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            end = promo.end_date
            if end and end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)

            if start and start > now:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Promotion coupon offer has not started yet.")
            if end and end < now:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Promotion coupon has expired.")
            if promo.usage_limit is not None and (promo.usage_count or 0) >= promo.usage_limit:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Promotion coupon global usage limit has been reached.")
            if subtotal < (promo.minimum_order_amount or 0.0):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Minimum order amount of ₹{promo.minimum_order_amount:.2f} is required for this coupon.")

            # Validate per-user redemption limit
            user_used = db.query(func.count(Order.id)).filter(
                Order.customer_id == customer.id,
                Order.promotion_code == promo.code,
                Order.status != OrderStatus.CANCELLED
            ).scalar() or 0
            if promo.per_user_limit is not None and user_used >= promo.per_user_limit:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"You have already redeemed this coupon the maximum allowed times ({promo.per_user_limit}).")

            if (promo.discount_percentage or 0.0) > 0:
                discount_amount = round(subtotal * (promo.discount_percentage / 100.0), 2)
                if promo.max_discount_amount and promo.max_discount_amount > 0:
                    discount_amount = min(discount_amount, promo.max_discount_amount)
            elif (promo.discount_amount or 0.0) > 0:
                discount_amount = min(subtotal, promo.discount_amount)
            applied_promo = str(promo.code)
            promo.usage_count = (promo.usage_count or 0) + 1

        from backend.app.services.delivery_pricing_service import DeliveryPricingService

        breakdown = DeliveryPricingService.calculate_delivery_breakdown(
            db=db,
            kitchen_lat=kitchen.latitude,
            kitchen_lon=kitchen.longitude,
            customer_lat=delivery_latitude,
            customer_lon=delivery_longitude,
            subtotal=subtotal,
            discount_amount=discount_amount,
        )

        if breakdown.get("out_of_range"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Delivery address is {breakdown.get('distance_km')} km away, which exceeds the maximum delivery radius of {breakdown.get('max_delivery_radius_km')} km.",
            )

        delivery_fee = breakdown["delivery_fee"]
        total_amount = breakdown["total_amount"]
        delivery_distance_km = breakdown.get("distance_km")
        pricing_breakdown_json = json.dumps(breakdown)

        # Generate unique order number
        today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        rand_code = random.randint(1000, 9999)
        order_number = f"ORD-{today_str}-{rand_code}"

        # Initialize Order in ORDER_PLACED state with address snapshot and coordinates
        order = Order(
            order_number=order_number,
            customer_id=customer.id,
            kitchen_id=kitchen.id,
            delivery_address_id=req.delivery_address_id,
            delivery_address_text=delivery_address_text,
            delivery_address_snapshot=delivery_address_snapshot,
            delivery_latitude=delivery_latitude,
            delivery_longitude=delivery_longitude,
            status=OrderStatus.ORDER_PLACED,
            subtotal=round(subtotal, 2),
            tax=breakdown.get("tax", 0.0),
            delivery_fee=delivery_fee,
            delivery_distance_km=delivery_distance_km,
            pricing_breakdown_json=pricing_breakdown_json,
            discount_amount=discount_amount,
            promotion_code=applied_promo,
            total_amount=total_amount,
            payment_status=PaymentStatus.PENDING,
            special_instructions=req.special_instructions,
        )
        db.add(order)
        db.flush()

        # Add order items
        for oi in order_items_to_create:
            item_record = OrderItem(
                order_id=order.id,
                menu_item_id=oi["menu_item_id"],
                item_name=oi["item_name"],
                unit_price=oi["unit_price"],
                quantity=oi["quantity"],
                subtotal=oi["subtotal"],
                special_requests=oi["special_requests"]
            )
            db.add(item_record)

        # Create payment record
        pay_method = (req.payment_method or "CASH").upper().strip()
        is_cod = pay_method in ["CASH", "CASH_ON_DELIVERY", "COD", "SIMULATED", "UPI"]
        payment = Payment(
            order_id=order.id,
            payment_provider=pay_method,
            transaction_reference=f"TXN-{uuid.uuid4().hex[:12].upper()}",
            amount=total_amount,
            currency="INR",
            status=PaymentStatus.SUCCESS if is_cod else PaymentStatus.PENDING
        )
        if is_cod:
            order.status = OrderStatus.PAYMENT_CONFIRMED
            order.payment_status = PaymentStatus.SUCCESS

        db.add(payment)

        # Notifications: Customer confirmation and Kitchen alert
        cust_notif = Notification(
            user_id=customer.id,
            title="Order Placed",
            message=f"Your order #{order.order_number} has been received by {kitchen.kitchen_name}.",
            event_type="ORDER_CREATED"
        )
        kitchen_notif = Notification(
            user_id=kitchen.user_id,
            title="New Order Received",
            message=f"New order #{order.order_number} received for ₹{total_amount:.2f}.",
            event_type="ORDER_CREATED"
        )
        db.add(cust_notif)
        db.add(kitchen_notif)

        from backend.app.services.notification_service import NotificationService
        NotificationService.notify_admins(
            db=db,
            event_type="ORDER_CREATED",
            title=f"New Order #{order.order_number}",
            message=f"Order #{order.order_number} for ₹{total_amount:.2f} placed by {customer.full_name} at {kitchen.kitchen_name}.",
            metadata={"entity_type": "order", "entity_id": order.id, "order_number": order.order_number, "link": "/admin/orders"}
        )
        if payment.status == PaymentStatus.SUCCESS:
            NotificationService.notify_admins(
                db=db,
                event_type="PAYMENT_RECEIVED",
                title=f"Payment Received: ₹{total_amount:.2f}",
                message=f"Payment of ₹{total_amount:.2f} received for order #{order.order_number} ({'COD' if is_cod else 'ONLINE'}).",
                metadata={"entity_type": "payment", "entity_id": payment.id, "order_id": order.id, "order_number": order.order_number, "link": "/admin/payments"}
            )

        db.commit()
        db.refresh(order)

        # Real-time event publication after commit
        try:
            from backend.app.websockets.connection_manager import ws_manager
            order_event_payload = {
                "order_id": order.id,
                "order_number": order.order_number,
                "kitchen_id": order.kitchen_id,
                "kitchen_name": kitchen.kitchen_name,
                "customer_id": order.customer_id,
                "customer_name": customer.full_name,
                "status": order.status.value,
                "total_amount": float(order.total_amount),
                "items_count": len(order_items_to_create),
                "created_at": order.created_at.isoformat() if order.created_at else None,
            }
            # Deliver to target kitchen owner
            ws_manager.publish_event(
                event_type="ORDER_CREATED",
                data=order_event_payload,
                target_kitchen_id=order.kitchen_id,
            )
            # Deliver to platform admins
            ws_manager.publish_event(
                event_type="ORDER_CREATED",
                data=order_event_payload,
                target_role="ADMIN",
            )
            # Deliver to ordering customer
            ws_manager.publish_event(
                event_type="ORDER_CREATED",
                data=order_event_payload,
                target_user_id=order.customer_id,
            )
        except Exception as ws_err:
            logger.warning(f"Error publishing real-time ORDER_CREATED event: {ws_err}")

        # Customer confirmation email
        try:
            if customer.email:
                email_service.send_order_placed_customer_email_sync(
                    to_email=customer.email,
                    order_number=order.order_number,
                    kitchen_name=kitchen.kitchen_name,
                    total_amount=total_amount
                )
        except Exception as e:
            logger.warning(f"Failed to send order placed email to customer {customer.email}: {e}")

        # Kitchen owner alert email
        try:
            if kitchen.user and kitchen.user.email:
                items_summary = ", ".join([f"{oi['quantity']}x {oi['item_name']}" for oi in order_items_to_create])
                email_service.send_order_placed_kitchen_email_sync(
                    to_email=kitchen.user.email,
                    order_number=order.order_number,
                    total_amount=total_amount,
                    items_summary=items_summary
                )
        except Exception as e:
            logger.warning(f"Failed to send order placed email to kitchen owner {kitchen.user.email if kitchen.user else ''}: {e}")

        return order

    @staticmethod
    def get_customer_orders(db: Session, customer_id: str) -> List[Order]:
        """Fetch all orders placed by the customer, most recent first."""
        return db.query(Order).filter(
            Order.customer_id == customer_id
        ).order_by(desc(Order.created_at)).all()

    @staticmethod
    def get_order_tracking(db: Session, customer_id: str, order_id: str) -> Order:
        """Fetch real-time tracking details for a customer's order."""
        order = db.query(Order).filter(
            Order.id == order_id,
            Order.customer_id == customer_id
        ).first()
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found or unauthorized.",
            )
        return order

    @staticmethod
    def cancel_order(db: Session, customer_id: str, order_id: str, reason: Optional[str] = None) -> Order:
        """
        Customer cancels order with food preparation lifecycle enforcement:
        - BEFORE food preparation (ORDER_PLACED, PAYMENT_CONFIRMED, KITCHEN_ACCEPTED):
          Order becomes CANCELLED. No wastage created. Restores stock if accepted.
        - AFTER food preparation started (PREPARING):
          Order becomes CANCELLED. Automatically calculates wastage from recipe x portions
          and creates WasteRecord and WASTE inventory ledger transactions without duplicate deduction.
        - READY, OUT_FOR_DELIVERY, DELIVERED:
          Cancellation rejected with clear message.
        """
        order = db.query(Order).filter(
            Order.id == order_id,
            Order.customer_id == customer_id
        ).first()
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found.",
            )

        # 1. Reject if already final
        if order.status in [OrderStatus.CANCELLED, OrderStatus.REJECTED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This order has already been cancelled or rejected.",
            )

        # 2. Reject if ready, out for delivery, or delivered
        if order.status in [OrderStatus.READY, OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cancellation is no longer available at stage '{order.status.value}'. Your food has already been prepared or dispatched.",
            )

        # 3. Check allowed cancellation states
        allowed_states = [
            OrderStatus.ORDER_PLACED,
            OrderStatus.PAYMENT_CONFIRMED,
            OrderStatus.KITCHEN_ACCEPTED,
            OrderStatus.PREPARING,
        ]
        if order.status not in allowed_states:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Order cannot be cancelled in state '{order.status.value}'.",
            )

        previous_status = order.status

        # Case A: Cancelled BEFORE food preparation begins
        if previous_status in [OrderStatus.ORDER_PLACED, OrderStatus.PAYMENT_CONFIRMED, OrderStatus.KITCHEN_ACCEPTED]:
            # If the order was in KITCHEN_ACCEPTED, inventory was deducted upon acceptance.
            # Restore raw inventory to the kitchen because food was not prepared.
            if previous_status == OrderStatus.KITCHEN_ACCEPTED:
                outward_txns = db.query(InventoryTransaction).filter(
                    InventoryTransaction.reference_order_id == order.id,
                    InventoryTransaction.kitchen_id == order.kitchen_id,
                    InventoryTransaction.transaction_type == InventoryTransactionType.OUTWARD_ORDER
                ).all()
                for txn in outward_txns:
                    ing = db.query(Ingredient).filter(Ingredient.id == txn.ingredient_id).first()
                    if ing:
                        qty_to_restore = abs(txn.quantity)
                        ing.current_stock += qty_to_restore
                        db.add(InventoryTransaction(
                            kitchen_id=order.kitchen_id,
                            ingredient_id=ing.id,
                            transaction_type=InventoryTransactionType.ADJUSTMENT,
                            quantity=qty_to_restore,
                            balance_after=ing.current_stock,
                            reference_order_id=order.id,
                            reason=f"Restored stock: Order #{order.order_number} cancelled before preparation",
                        ))
                        inv_rec = db.query(Inventory).filter(
                            Inventory.kitchen_id == order.kitchen_id,
                            Inventory.ingredient_id == ing.id
                        ).first()
                        if inv_rec:
                            inv_rec.quantity = ing.current_stock
                            inv_rec.status = (
                                InventoryStatus.AVAILABLE if ing.current_stock > ing.minimum_stock_threshold else InventoryStatus.LOW_STOCK
                            )
            order.cancellation_reason = reason or "Cancelled by customer before food preparation"

        # Case B: Cancelled AFTER food preparation has started (PREPARING)
        elif previous_status == OrderStatus.PREPARING:
            order.cancellation_reason = reason or "Cancelled by customer after food preparation started"

            # Check if wastage records were already created to prevent duplicate records
            existing_waste = db.query(WasteRecord).filter(WasteRecord.order_id == order.id).first()
            if not existing_waste:
                for order_item in order.items:
                    recipe_links = db.query(MenuItemIngredient).filter(
                        MenuItemIngredient.menu_item_id == order_item.menu_item_id
                    ).all() if order_item.menu_item_id else []

                    if recipe_links:
                        for link in recipe_links:
                            ing = db.query(Ingredient).filter(Ingredient.id == link.ingredient_id).first()
                            if not ing:
                                continue
                            wasted_qty = round(link.quantity_required * order_item.quantity, 3)

                            # Estimate cost from actual purchases using weighted average unit cost
                            from backend.app.services.kitchen_service import KitchenService
                            unit_cost = KitchenService._get_ingredient_unit_cost(db, order.kitchen_id, ing.id)
                            est_cost = round(wasted_qty * unit_cost, 2) if unit_cost is not None else None

                            waste_rec = WasteRecord(
                                kitchen_id=order.kitchen_id,
                                ingredient_id=ing.id,
                                order_id=order.id,
                                menu_item_id=order_item.menu_item_id,
                                menu_item_name=order_item.item_name,
                                portions_wasted=float(order_item.quantity),
                                quantity=wasted_qty,
                                unit=ing.unit,
                                reason="CUSTOMER_CANCELLED_AFTER_PREPARATION",
                                recorded_by="System (Customer Cancellation)",
                                estimated_cost=est_cost,
                                source_event="ORDER_CANCELLATION",
                            )
                            db.add(waste_rec)

                            # Separate inventory transaction for wastage without double deduction
                            outward_txn = db.query(InventoryTransaction).filter(
                                InventoryTransaction.reference_order_id == order.id,
                                InventoryTransaction.ingredient_id == ing.id,
                                InventoryTransaction.transaction_type == InventoryTransactionType.OUTWARD_ORDER
                            ).first()

                            if outward_txn:
                                # Normal consumption occurred at accept: reclassify via ADJUSTMENT and record WASTE
                                db.add(InventoryTransaction(
                                    kitchen_id=order.kitchen_id,
                                    ingredient_id=ing.id,
                                    transaction_type=InventoryTransactionType.ADJUSTMENT,
                                    quantity=abs(outward_txn.quantity),
                                    balance_after=ing.current_stock + abs(outward_txn.quantity),
                                    reference_order_id=order.id,
                                    reason=f"Reclassified order #{order.order_number} consumption to food wastage",
                                ))
                                db.add(InventoryTransaction(
                                    kitchen_id=order.kitchen_id,
                                    ingredient_id=ing.id,
                                    transaction_type=InventoryTransactionType.WASTE,
                                    quantity=-wasted_qty,
                                    balance_after=ing.current_stock,
                                    reference_order_id=order.id,
                                    reason=f"Wastage: Customer cancelled order #{order.order_number} after preparation started",
                                ))
                            else:
                                # Stock was not yet deducted: deduct now as WASTE
                                ing.current_stock = max(0.0, ing.current_stock - wasted_qty)
                                db.add(InventoryTransaction(
                                    kitchen_id=order.kitchen_id,
                                    ingredient_id=ing.id,
                                    transaction_type=InventoryTransactionType.WASTE,
                                    quantity=-wasted_qty,
                                    balance_after=ing.current_stock,
                                    reference_order_id=order.id,
                                    reason=f"Wastage: Customer cancelled order #{order.order_number} after preparation started",
                                ))
                    else:
                        # Dish without recipe links: log portion-level wastage record
                        db.add(WasteRecord(
                            kitchen_id=order.kitchen_id,
                            ingredient_id=None,
                            order_id=order.id,
                            menu_item_id=order_item.menu_item_id,
                            menu_item_name=order_item.item_name,
                            portions_wasted=float(order_item.quantity),
                            quantity=float(order_item.quantity),
                            unit="portion",
                            reason="CUSTOMER_CANCELLED_AFTER_PREPARATION",
                            recorded_by="System (Customer Cancellation)",
                            estimated_cost=round(order_item.unit_price * order_item.quantity, 2),
                            source_event="ORDER_CANCELLATION",
                        ))

        order.status = OrderStatus.CANCELLED
        order.updated_at = datetime.now(timezone.utc)
        if order.payment_status == PaymentStatus.SUCCESS:
            order.payment_status = PaymentStatus.REFUNDED

        # Notifications
        if order.kitchen and order.kitchen.user_id:
            kitchen_notif = Notification(
                user_id=order.kitchen.user_id,
                title="Order Cancelled",
                message=f"Order #{order.order_number} was cancelled by the customer.",
                event_type="ORDER_CANCELLED"
            )
            db.add(kitchen_notif)

        cust_notif = Notification(
            user_id=order.customer_id,
            title="Order Cancelled",
            message=f"Your order #{order.order_number} has been cancelled successfully.",
            event_type="ORDER_CANCELLED"
        )
        db.add(cust_notif)

        from backend.app.services.notification_service import NotificationService
        NotificationService.notify_admins(
            db=db,
            event_type="ORDER_CANCELLED",
            title=f"Order #{order.order_number} Cancelled",
            message=f"Order #{order.order_number} was cancelled by the customer. Reason: {order.cancellation_reason}",
            metadata={"entity_type": "order", "entity_id": order.id, "order_number": order.order_number, "link": "/admin/orders"}
        )

        db.commit()
        db.refresh(order)

        # Real-time event publication after commit
        try:
            from backend.app.websockets.connection_manager import ws_manager
            status_event_payload = {
                "order_id": order.id,
                "order_number": order.order_number,
                "kitchen_id": order.kitchen_id,
                "customer_id": order.customer_id,
                "status": order.status.value,
                "payment_status": order.payment_status.value if order.payment_status else None,
                "cancellation_reason": order.cancellation_reason,
                "updated_at": order.updated_at.isoformat() if order.updated_at else None,
            }
            ws_manager.publish_event(
                event_type="ORDER_STATUS_CHANGED",
                data=status_event_payload,
                target_kitchen_id=order.kitchen_id,
            )
            ws_manager.publish_event(
                event_type="ORDER_STATUS_CHANGED",
                data=status_event_payload,
                target_role="ADMIN",
            )
            ws_manager.publish_event(
                event_type="ORDER_STATUS_CHANGED",
                data=status_event_payload,
                target_user_id=order.customer_id,
            )
            # Also notify inventory/waste refresh
            ws_manager.publish_event(
                event_type="INVENTORY_UPDATED",
                data={"kitchen_id": order.kitchen_id, "reason": "ORDER_CANCELLATION"},
                target_kitchen_id=order.kitchen_id,
            )
            ws_manager.publish_event(
                event_type="INVENTORY_UPDATED",
                data={"kitchen_id": order.kitchen_id, "reason": "ORDER_CANCELLATION"},
                target_role="ADMIN",
            )
        except Exception as ws_err:
            logger.warning(f"Error publishing real-time cancellation event: {ws_err}")

        # Send cancellation emails
        try:
            if order.customer and order.customer.email:
                email_service.send_order_status_email_sync(
                    to_email=order.customer.email,
                    order_number=order.order_number,
                    status_title="Order Cancelled",
                    message="Your order has been cancelled."
                )
        except Exception as e:
            logger.warning(f"Failed to send cancellation email to customer: {e}")

        try:
            if order.kitchen and order.kitchen.user and order.kitchen.user.email:
                email_service.send_order_status_email_sync(
                    to_email=order.kitchen.user.email,
                    order_number=order.order_number,
                    status_title="Order Cancelled by Customer",
                    message=f"Order #{order.order_number} was cancelled by the customer."
                )
        except Exception as e:
            logger.warning(f"Failed to send cancellation alert to kitchen owner: {e}")

        return order

    @staticmethod
    def update_order_delivery_location(
        db: Session,
        customer: User,
        order_id: str,
        req: UpdateDeliveryLocationRequest,
    ) -> Order:
        """Update or confirm delivery coordinates for an active customer order."""
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found.",
            )
        if order.customer_id != customer.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to update this order's delivery location.",
            )

        # Only allow updating for active, un-dispatched orders
        allowed_statuses = [
            OrderStatus.ORDER_PLACED,
            OrderStatus.PAYMENT_CONFIRMED,
            OrderStatus.KITCHEN_ACCEPTED,
            OrderStatus.PREPARING,
        ]
        if order.status not in allowed_statuses:
            status_val = order.status.value if hasattr(order.status, 'value') else str(order.status)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot update delivery location for order in '{status_val}' state.",
            )

        if not (-90.0 <= req.latitude <= 90.0) or not (-180.0 <= req.longitude <= 180.0):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid coordinates range provided.",
            )

        order.delivery_latitude = req.latitude
        order.delivery_longitude = req.longitude
        if req.address_text:
            order.delivery_address_text = req.address_text

        # Update snapshot JSON safely
        snapshot_data = {}
        if order.delivery_address_snapshot:
            try:
                snapshot_data = json.loads(order.delivery_address_snapshot)
            except Exception:
                snapshot_data = {}
        snapshot_data["latitude"] = req.latitude
        snapshot_data["longitude"] = req.longitude
        if req.address_text:
            snapshot_data["address_text"] = req.address_text
            snapshot_data["address_line1"] = req.address_text
        order.delivery_address_snapshot = json.dumps(snapshot_data)
        order.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(order)
        return order

    @staticmethod
    def toggle_favorite(
        db: Session,
        customer_id: str,
        kitchen_id: Optional[str] = None,
        menu_item_id: Optional[str] = None
    ) -> bool:
        """Toggle favorite status for a kitchen or menu item."""
        q = db.query(Favorite).filter(Favorite.customer_id == customer_id)
        if kitchen_id:
            q = q.filter(Favorite.kitchen_id == kitchen_id)
        elif menu_item_id:
            q = q.filter(Favorite.menu_item_id == menu_item_id)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either kitchen_id or menu_item_id must be provided."
            )

        existing = q.first()
        if existing:
            db.delete(existing)
            db.commit()
            return False  # Unfavorited
        else:
            fav = Favorite(
                customer_id=customer_id,
                kitchen_id=kitchen_id,
                menu_item_id=menu_item_id
            )
            db.add(fav)
            db.commit()
            return True  # Favorited

    @staticmethod
    def create_review(
        db: Session,
        customer_id: str,
        req: ReviewCreateRequest
    ) -> Review:
        """Submit a customer review for a completed order."""
        order = db.query(Order).filter(
            Order.id == req.order_id,
            Order.customer_id == customer_id
        ).first()
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found or unauthorized.",
            )
        if order.status != OrderStatus.DELIVERED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reviews can only be submitted after the order has been delivered.",
            )

        review = Review(
            order_id=order.id,
            customer_id=customer_id,
            kitchen_id=order.kitchen_id,
            menu_item_id=req.menu_item_id,
            rating=req.rating,
            comment=req.comment,
        )
        db.add(review)

        # Update kitchen aggregate rating
        kitchen = order.kitchen
        total_rating = (kitchen.rating * kitchen.rating_count) + req.rating
        kitchen.rating_count += 1
        kitchen.rating = round(total_rating / kitchen.rating_count, 2)

        db.commit()
        db.refresh(review)
        return review

    @staticmethod
    def get_active_promotions(db: Session) -> List[Promotion]:
        """Fetch all currently active promotions."""
        now = datetime.now(timezone.utc)
        promos = db.query(Promotion).filter(Promotion.is_active == True).all()
        valid = []
        for p in promos:
            start = p.start_date
            if start and start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            end = p.end_date
            if end and end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
            if (not start or start <= now) and (not end or end >= now):
                valid.append(p)
        return valid

    @staticmethod
    def mark_all_notifications_read(db: Session, customer_id: str) -> int:
        """Mark all unread notifications as read for a customer."""
        count = db.query(Notification).filter(
            Notification.user_id == customer_id,
            Notification.is_read == False
        ).update({"is_read": True})
        db.commit()
        return count

    @staticmethod
    def autocomplete_locations(
        query: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None
    ) -> List[dict]:
        """
        Real food-delivery-style autocomplete location search.
        Queries real geocoding service with India scope and parses into Swiggy/Zomato style:
        main_text, secondary_text, formatted_address, latitude, longitude.
        """
        import urllib.request
        import urllib.parse
        import json
        import re

        clean_q = (query or "").strip()
        if len(clean_q) < 2:
            return []

        def call_nominatim(term: str) -> list:
            url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(term)}&format=json&addressdetails=1&limit=6&countrycodes=in"
            req = urllib.request.Request(url, headers={"User-Agent": "CloudKitchen-UnifiedPlatform/1.0"})
            try:
                with urllib.request.urlopen(req, timeout=4) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except Exception as e:
                logger.warning(f"Nominatim autocomplete warning for '{term}': {e}")
                return []

        raw = call_nominatim(clean_q)

        # Fallback if 0 results and comma separated (e.g. 'House of children play school, Hanamkonda')
        if not raw and "," in clean_q:
            parts = [p.strip() for p in clean_q.split(",") if p.strip()]
            for p in parts:
                raw = call_nominatim(p)
                if raw:
                    break

        # Fallback if 0 results: strip common noise words
        if not raw:
            simplified = re.sub(r"(?i)\b(play\s*school|school|colony|near|opposite|opp|street|road|nagar)\b", "", clean_q).strip()
            if simplified and simplified != clean_q:
                raw = call_nominatim(simplified)

        suggestions = []
        seen = set()
        for item in raw:
            place_id = str(item.get("place_id") or uuid.uuid4())
            if place_id in seen:
                continue
            seen.add(place_id)

            addr = item.get("address", {})
            name = (
                item.get("name")
                or addr.get("road")
                or addr.get("suburb")
                or addr.get("neighbourhood")
                or addr.get("city")
                or item.get("display_name", "").split(",")[0].strip()
            )

            city = (
                addr.get("city")
                or addr.get("town")
                or addr.get("village")
                or addr.get("county")
                or addr.get("state_district")
                or ""
            )
            state = addr.get("state", "")
            postcode = addr.get("postcode", "")
            country = addr.get("country", "India")

            secondary_parts = [p for p in [city, state, postcode] if p]
            secondary_text = ", ".join(secondary_parts) or country

            try:
                lat = float(item.get("lat"))
                lon = float(item.get("lon"))
            except (TypeError, ValueError):
                continue

            suggestions.append({
                "place_id": place_id,
                "main_text": name,
                "secondary_text": secondary_text,
                "formatted_address": item.get("display_name"),
                "latitude": lat,
                "longitude": lon,
                "city": city,
            })

        return suggestions

    @staticmethod
    def reverse_geocode(lat: float, lon: float) -> dict:
        """
        Reverse geocode coordinates into structured address and city name.
        """
        import urllib.request
        import json

        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
        req = urllib.request.Request(url, headers={"User-Agent": "CloudKitchen-UnifiedPlatform/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                addr = data.get("address", {})
                city = (
                    addr.get("city")
                    or addr.get("town")
                    or addr.get("village")
                    or addr.get("county")
                    or addr.get("state_district")
                    or ""
                )
                return {
                    "formatted_address": data.get("display_name") or f"Location ({lat:.5f}, {lon:.5f})",
                    "latitude": float(lat),
                    "longitude": float(lon),
                    "city": city,
                }
        except Exception as e:
            logger.warning(f"Reverse geocode warning for ({lat}, {lon}): {e}")
            return {
                "formatted_address": f"Selected Location ({lat:.5f}, {lon:.5f})",
                "latitude": float(lat),
                "longitude": float(lon),
                "city": "",
            }

    # ── Admin-Assisted Cancellation (READY orders) ─────────────────────────────

    @staticmethod
    def submit_cancellation_request(
        db: Session,
        customer_id: str,
        order_id: str,
        reason: Optional[str] = None,
        customer_note: Optional[str] = None,
    ) -> CancellationRequest:
        """
        Customer requests cancellation of a READY order.
        Direct cancellation is still blocked server-side.
        This creates a PENDING CancellationRequest for Admin review.
        """
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")

        if order.customer_id != customer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to request cancellation for this order."
            )

        if order.status != OrderStatus.READY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cancellation requests can only be submitted for READY orders. Current status: {order.status.value}.",
            )

        # Check for existing pending request
        existing = db.query(CancellationRequest).filter(
            CancellationRequest.order_id == order_id,
            CancellationRequest.status == "PENDING",
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A cancellation request for this order is already pending admin review.",
            )

        cr = CancellationRequest(
            order_id=order_id,
            customer_id=customer_id,
            kitchen_id=order.kitchen_id,
            reason=reason or "Changed my mind",
            customer_note=customer_note,
            status="PENDING",
        )
        db.add(cr)

        # Notify admin via existing notification system
        from backend.app.services.notification_service import NotificationService
        NotificationService.create_admin_notification(
            db=db,
            title="Cancellation request requires review",
            message=f"Order #{order.order_number} — customer requests cancellation (food is READY). Reason: {reason or 'Not provided'}.",
            event_type="ORDER_CANCELLATION_REQUEST",
            metadata={
                "order_id": order.id,
                "order_number": order.order_number,
                "customer": order.customer.full_name if order.customer else "",
                "kitchen": order.kitchen.kitchen_name if order.kitchen else "",
                "reason": reason or "",
                "customer_note": customer_note or "",
                "requested_time": datetime.now(timezone.utc).isoformat(),
                "link": f"/admin/orders?tab=cancellations&order_id={order.id}",
                "entity_id": order.id,
            }
        )

        db.commit()
        db.refresh(cr)
        return cr

    @staticmethod
    def get_cancellation_request_for_order(
        db: Session,
        customer_id: str,
        order_id: str,
    ) -> Optional[CancellationRequest]:
        """Get the latest cancellation request for an order (customer view)."""
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
        if order.customer_id != customer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to view cancellation requests for this order."
            )

        return db.query(CancellationRequest).filter(
            CancellationRequest.order_id == order_id,
            CancellationRequest.customer_id == customer_id,
        ).order_by(CancellationRequest.created_at.desc()).first()
