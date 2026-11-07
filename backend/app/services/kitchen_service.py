"""
Kitchen Owner Service — Phase 4.
Implements all kitchen-owner-scoped business logic:
  - Dashboard statistics (live from DB, no fabricated values)
  - Kitchen-specific order queue with state-machine transitions
  - Accept / reject orders + inventory consumption on acceptance
  - PREPARING to READY transitions
  - Menu item CRUD (kitchen-scoped)
  - Kitchen-defined ingredient CRUD + inventory ledger
  - Restocking recommendations
  - Waste record logging
  - Kitchen notifications
"""
import logging
from datetime import datetime, timezone, date, timedelta
import calendar
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

logger = logging.getLogger(__name__)

from backend.app.models.enums import (
    OrderStatus,
    InventoryStatus,
    InventoryTransactionType,
)
from backend.app.models.user import User, KitchenProfile
from backend.app.models.menu import MenuItem, Ingredient, MenuItemIngredient
from backend.app.models.inventory import Inventory, InventoryTransaction, Purchase, WasteRecord
from backend.app.models.order import Order
from backend.app.models.platform import Notification
from backend.app.schemas.kitchen import (
    KitchenDashboardStats,
    MenuItemCreate,
    MenuItemUpdate,
    IngredientCreate,
    IngredientUpdate,
    InventoryRestockRequest,
    WasteRecordCreate,
    KitchenSettingsUpdate,
    RestockingRecommendation,
    RecipeLinkRequest,
    WasteAnalyticsResponse,
    WasteByReasonItem,
    WasteByMenuItem,
    WasteByIngredientItem,
    MonthlyWasteTrendItem,
    DeliveryRouteResponse,
    DeliveryLocationInfo,
)
from backend.app.core.email import email_service

KITCHEN_VALID_TRANSITIONS: dict = {
    OrderStatus.ORDER_PLACED: [OrderStatus.KITCHEN_ACCEPTED, OrderStatus.REJECTED],
    OrderStatus.PAYMENT_CONFIRMED: [OrderStatus.KITCHEN_ACCEPTED, OrderStatus.REJECTED],
    OrderStatus.KITCHEN_ACCEPTED: [OrderStatus.PREPARING, OrderStatus.REJECTED],
    OrderStatus.PREPARING: [OrderStatus.READY],
    OrderStatus.READY: [OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED],
    OrderStatus.OUT_FOR_DELIVERY: [OrderStatus.DELIVERED],
}


def _utc_now():
    return datetime.now(timezone.utc)


def _today_start():
    today = date.today()
    return datetime(today.year, today.month, today.day, tzinfo=timezone.utc)


class KitchenService:

    @staticmethod
    def _get_kitchen_profile(db: Session, user: User, require_approved: bool = True) -> KitchenProfile:
        profile = db.query(KitchenProfile).filter(KitchenProfile.user_id == user.id).first()
        if not profile:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kitchen profile not found.")
        if require_approved:
            if not profile.is_approved:
                status_msg = getattr(profile, "approval_status", "PENDING_APPROVAL")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Kitchen account is not approved. Current status: {status_msg}. Please wait for admin approval.",
                )
            if profile.license:
                from backend.app.services.fssai_service import FssaiService
                from backend.app.models.enums import LicenseStatus
                FssaiService.sync_license_expiration(db, profile.license)
                if profile.license.status == LicenseStatus.EXPIRED:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Kitchen operations are blocked: FSSAI Food License has expired. Please renew your license."
                    )
                if profile.license.status == LicenseStatus.CORRECTION_REQUIRED:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Kitchen operations are blocked: License correction required. Reason: {profile.license.correction_reason}"
                    )
                if profile.license.status != LicenseStatus.VERIFIED:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Kitchen operations are blocked: FSSAI Food License is not verified (Status: {profile.license.status})."
                    )
        return profile

    @staticmethod
    def _assert_kitchen_order(db: Session, kitchen_id: str, order_id: str) -> Order:
        order = db.query(Order).filter(Order.id == order_id, Order.kitchen_id == kitchen_id).first()
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found in your kitchen.")
        return order

    @staticmethod
    def _assert_kitchen_ingredient(db: Session, kitchen_id: str, ingredient_id: str) -> Ingredient:
        ingredient = db.query(Ingredient).filter(
            Ingredient.id == ingredient_id, Ingredient.kitchen_id == kitchen_id
        ).first()
        if not ingredient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingredient not found in your kitchen.")
        return ingredient

    @staticmethod
    def get_dashboard_stats(db: Session, user: User) -> KitchenDashboardStats:
        kitchen = KitchenService._get_kitchen_profile(db, user)
        today_start = _today_start()

        pending_count = db.query(func.count(Order.id)).filter(
            Order.kitchen_id == kitchen.id,
            Order.status.in_([OrderStatus.ORDER_PLACED, OrderStatus.PAYMENT_CONFIRMED]),
        ).scalar() or 0

        active_count = db.query(func.count(Order.id)).filter(
            Order.kitchen_id == kitchen.id,
            Order.status.in_([OrderStatus.KITCHEN_ACCEPTED, OrderStatus.PREPARING, OrderStatus.READY]),
        ).scalar() or 0

        completed_today = db.query(func.count(Order.id)).filter(
            Order.kitchen_id == kitchen.id,
            Order.status == OrderStatus.DELIVERED,
            Order.updated_at >= today_start,
        ).scalar() or 0

        revenue_row = db.query(func.sum(Order.total_amount)).filter(
            Order.kitchen_id == kitchen.id,
            Order.status == OrderStatus.DELIVERED,
            Order.updated_at >= today_start,
        ).scalar()
        revenue_today = float(revenue_row) if revenue_row else 0.0

        total_menu_items = db.query(func.count(MenuItem.id)).filter(
            MenuItem.kitchen_id == kitchen.id
        ).scalar() or 0

        low_stock_count = db.query(func.count(Ingredient.id)).filter(
            Ingredient.kitchen_id == kitchen.id,
            Ingredient.current_stock <= Ingredient.minimum_stock_threshold,
        ).scalar() or 0

        unread_notifs = db.query(func.count(Notification.id)).filter(
            Notification.user_id == user.id, Notification.is_read == False
        ).scalar() or 0

        return KitchenDashboardStats(
            kitchen_id=kitchen.id,
            kitchen_name=kitchen.kitchen_name,
            is_open=kitchen.is_open,
            rating=kitchen.rating,
            rating_count=kitchen.rating_count,
            pending_orders_count=pending_count,
            active_orders_count=active_count,
            completed_orders_today=completed_today,
            revenue_today=revenue_today,
            total_menu_items=total_menu_items,
            low_stock_count=low_stock_count,
            unread_notifications_count=unread_notifs,
        )

    @staticmethod
    def get_order_queue(db: Session, user: User, status_filter=None) -> List[Order]:
        kitchen = KitchenService._get_kitchen_profile(db, user)
        q = db.query(Order).filter(Order.kitchen_id == kitchen.id)
        if status_filter:
            q = q.filter(Order.status.in_(status_filter))
        return q.order_by(Order.created_at.asc()).all()

    @staticmethod
    def get_single_order(db: Session, user: User, order_id: str) -> Order:
        kitchen = KitchenService._get_kitchen_profile(db, user)
        return KitchenService._assert_kitchen_order(db, kitchen.id, order_id)

    @staticmethod
    def accept_order(db: Session, user: User, order_id: str) -> Order:
        kitchen = KitchenService._get_kitchen_profile(db, user)
        order = KitchenService._assert_kitchen_order(db, kitchen.id, order_id)

        allowed = [OrderStatus.ORDER_PLACED, OrderStatus.PAYMENT_CONFIRMED]
        if order.status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Cannot accept order in status '{order.status.value}'.",
            )

        # 1. Prevent duplicate deduction if acceptance is retried
        existing_txns = db.query(InventoryTransaction).filter(
            InventoryTransaction.reference_order_id == order.id,
            InventoryTransaction.kitchen_id == kitchen.id,
            InventoryTransaction.transaction_type == InventoryTransactionType.OUTWARD_ORDER
        ).first()

        if not existing_txns:
            # 2. Pre-calculate total requirements across ALL order items
            ingredient_requirements: dict[str, float] = {}
            for order_item in order.items:
                if order_item.menu_item_id:
                    recipe_links = db.query(MenuItemIngredient).filter(
                        MenuItemIngredient.menu_item_id == order_item.menu_item_id
                    ).all()
                    for link in recipe_links:
                        link_unit = getattr(link, "unit", None)
                        ing = link.ingredient or db.query(Ingredient).filter(Ingredient.id == link.ingredient_id).first()
                        if ing and link_unit and link_unit.strip().lower() != ing.unit.strip().lower():
                            from backend.app.core.unit_converter import convert_quantity
                            converted_req = convert_quantity(link.quantity_required, link_unit, ing.unit)
                        else:
                            converted_req = link.quantity_required
                        required_qty = converted_req * order_item.quantity
                        ingredient_requirements[link.ingredient_id] = (
                            ingredient_requirements.get(link.ingredient_id, 0.0) + required_qty
                        )

            # 3. Validate stock for ALL ingredients BEFORE any deduction (Atomicity)
            insufficient_items = []
            for ing_id, required_qty in ingredient_requirements.items():
                ingredient = db.query(Ingredient).filter(
                    Ingredient.id == ing_id,
                    Ingredient.kitchen_id == kitchen.id
                ).first()
                if not ingredient:
                    insufficient_items.append(f"Ingredient ID {ing_id} missing")
                elif ingredient.current_stock < required_qty:
                    insufficient_items.append(
                        f"'{ingredient.name}': required {required_qty:.2f} {ingredient.unit}, available {ingredient.current_stock:.2f} {ingredient.unit}"
                    )

            if insufficient_items:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient inventory stock to fulfill order: {'; '.join(insufficient_items)}",
                )

            # 4. Perform deduction only after confirming ALL stock is sufficient
            for ing_id, required_qty in ingredient_requirements.items():
                KitchenService._deduct_inventory(
                    db=db,
                    kitchen_id=kitchen.id,
                    ingredient_id=ing_id,
                    quantity=required_qty,
                    order_id=order.id,
                    reason=f"Consumed for order #{order.order_number}",
                    transaction_type=InventoryTransactionType.OUTWARD_ORDER,
                )

        order.status = OrderStatus.KITCHEN_ACCEPTED
        order.updated_at = _utc_now()

        # Database notifications
        db.add(Notification(
            user_id=order.customer_id,
            title="Order Accepted!",
            message=f"Your order #{order.order_number} has been accepted by {kitchen.kitchen_name}.",
            event_type="ORDER_ACCEPTED",
        ))
        db.add(Notification(
            user_id=user.id,
            title=f"Order #{order.order_number} Accepted",
            message=f"You accepted order #{order.order_number}. Ingredients deducted from inventory ledger.",
            event_type="ORDER_ACCEPTED",
        ))
        db.commit()
        db.refresh(order)

        # Real-time event publication after commit
        try:
            from backend.app.websockets.connection_manager import ws_manager
            order_payload = {
                "order_id": order.id,
                "order_number": order.order_number,
                "kitchen_id": order.kitchen_id,
                "customer_id": order.customer_id,
                "status": order.status.value,
                "updated_at": order.updated_at.isoformat() if order.updated_at else None,
            }
            ws_manager.publish_event(
                event_type="ORDER_STATUS_CHANGED",
                data=order_payload,
                target_user_id=order.customer_id,
            )
            ws_manager.publish_event(
                event_type="ORDER_STATUS_CHANGED",
                data=order_payload,
                target_kitchen_id=order.kitchen_id,
            )
            ws_manager.publish_event(
                event_type="ORDER_STATUS_CHANGED",
                data=order_payload,
                target_role="ADMIN",
            )
            # Notify inventory stock change from order ingredient deduction
            ws_manager.publish_event(
                event_type="INVENTORY_UPDATED",
                data={"kitchen_id": order.kitchen_id, "order_id": order.id, "reason": "ORDER_ACCEPTED_DEDUCTION"},
                target_kitchen_id=order.kitchen_id,
            )
            ws_manager.publish_event(
                event_type="INVENTORY_UPDATED",
                data={"kitchen_id": order.kitchen_id, "order_id": order.id, "reason": "ORDER_ACCEPTED_DEDUCTION"},
                target_role="ADMIN",
            )
        except Exception as ws_err:
            logger.warning(f"Error publishing real-time accept_order event: {ws_err}")

        # Note: Customer does NOT receive an email for ACCEPTED (KITCHEN_ACCEPTED).
        # Per customer order notification requirements, only 2 customer emails are sent per order:
        # 1. Order Placed (at creation)
        # 2. Order Delivered / Successful (when transitioned to DELIVERED)
        return order

    @staticmethod
    def reject_order(db: Session, user: User, order_id: str, rejection_reason: str) -> Order:
        kitchen = KitchenService._get_kitchen_profile(db, user)
        order = KitchenService._assert_kitchen_order(db, kitchen.id, order_id)

        allowed = [OrderStatus.ORDER_PLACED, OrderStatus.PAYMENT_CONFIRMED, OrderStatus.KITCHEN_ACCEPTED]
        if order.status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Cannot reject order in status '{order.status.value}'.",
            )

        order.status = OrderStatus.REJECTED
        order.rejection_reason = rejection_reason
        order.updated_at = _utc_now()

        db.add(Notification(
            user_id=order.customer_id,
            title="Order Rejected",
            message=f"Your order #{order.order_number} was rejected. Reason: {rejection_reason}",
            event_type="ORDER_REJECTED",
        ))

        from backend.app.services.notification_service import NotificationService
        NotificationService.notify_admins(
            db=db,
            event_type="ORDER_CANCELLED",
            title=f"Order #{order.order_number} Rejected by Kitchen",
            message=f"Order #{order.order_number} was rejected by {kitchen.kitchen_name}. Reason: {rejection_reason}",
            metadata={"entity_type": "order", "entity_id": order.id, "order_number": order.order_number, "link": "/admin/orders"}
        )

        db.commit()
        db.refresh(order)

        # Real-time event publication after commit
        try:
            from backend.app.websockets.connection_manager import ws_manager
            order_payload = {
                "order_id": order.id,
                "order_number": order.order_number,
                "kitchen_id": order.kitchen_id,
                "customer_id": order.customer_id,
                "status": order.status.value,
                "rejection_reason": rejection_reason,
                "updated_at": order.updated_at.isoformat() if order.updated_at else None,
            }
            ws_manager.publish_event(
                event_type="ORDER_STATUS_CHANGED",
                data=order_payload,
                target_user_id=order.customer_id,
            )
            ws_manager.publish_event(
                event_type="ORDER_STATUS_CHANGED",
                data=order_payload,
                target_kitchen_id=order.kitchen_id,
            )
            ws_manager.publish_event(
                event_type="ORDER_STATUS_CHANGED",
                data=order_payload,
                target_role="ADMIN",
            )
        except Exception as ws_err:
            logger.warning(f"Error publishing real-time reject_order event: {ws_err}")

        try:
            if order.customer and order.customer.email:
                email_service.send_order_status_email_sync(
                    to_email=order.customer.email,
                    order_number=order.order_number,
                    status_title="Rejected",
                    message=f"Your order #{order.order_number} could not be accepted. Reason: {rejection_reason}"
                )
        except Exception as e:
            logger.warning(f"Failed to send order rejection email to customer {order.customer.email if order.customer else ''}: {e}")

        return order

    @staticmethod
    def transition_order_status(db: Session, user: User, order_id: str, target_status: OrderStatus, reason: Optional[str] = None) -> Order:
        kitchen = KitchenService._get_kitchen_profile(db, user)
        order = KitchenService._assert_kitchen_order(db, kitchen.id, order_id)

        allowed_next = KITCHEN_VALID_TRANSITIONS.get(order.status, [])
        if target_status not in allowed_next:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid transition from '{order.status.value}' to '{target_status.value}'. Allowed: {[s.value for s in allowed_next]}.",
            )

        order.status = target_status
        order.updated_at = _utc_now()

        event_map = {
            OrderStatus.PREPARING: ("Order is Being Prepared", "ORDER_PREPARING", "Your food is being freshly prepared in the kitchen."),
            OrderStatus.READY: ("Order Ready!", "ORDER_READY", "Your order is prepared and ready for delivery/pickup."),
            OrderStatus.OUT_FOR_DELIVERY: ("Out for Delivery", "ORDER_OUT_FOR_DELIVERY", "Your order is on the way!"),
            OrderStatus.DELIVERED: ("Order Delivered", "ORDER_DELIVERED", "Your order has been delivered. Enjoy your meal!"),
        }
        if target_status in event_map:
            title, event_type, msg = event_map[target_status]
            db.add(Notification(
                user_id=order.customer_id,
                title=title,
                message=f"Order #{order.order_number}: {msg}",
                event_type=event_type,
            ))
            if target_status == OrderStatus.DELIVERED:
                from backend.app.services.notification_service import NotificationService
                NotificationService.notify_admins(
                    db=db,
                    event_type="ORDER_DELIVERED",
                    title=f"Order #{order.order_number} Delivered",
                    message=f"Order #{order.order_number} from {kitchen.kitchen_name} has been successfully delivered.",
                    metadata={"entity_type": "order", "entity_id": order.id, "order_number": order.order_number, "link": "/admin/orders"}
                )

                # Customer email notification: Order Successful (Delivered)
                # Customers receive only TWO emails per order: Order Placed and Order Successful (Delivered).
                # Intermediate statuses (PREPARING, READY, OUT_FOR_DELIVERY) do not trigger customer emails.
                try:
                    if order.customer and order.customer.email:
                        email_service.send_order_delivered_customer_email_sync(
                            to_email=order.customer.email,
                            order_number=order.order_number,
                            kitchen_name=kitchen.kitchen_name
                        )
                except Exception as e:
                    logger.warning(f"Failed to send order delivered email to customer {order.customer.email if order.customer else ''}: {e}")

        db.commit()
        db.refresh(order)

        # Real-time event publication after commit
        try:
            from backend.app.websockets.connection_manager import ws_manager
            order_payload = {
                "order_id": order.id,
                "order_number": order.order_number,
                "kitchen_id": order.kitchen_id,
                "customer_id": order.customer_id,
                "status": order.status.value,
                "updated_at": order.updated_at.isoformat() if order.updated_at else None,
            }
            ws_manager.publish_event(
                event_type="ORDER_STATUS_CHANGED",
                data=order_payload,
                target_user_id=order.customer_id,
            )
            ws_manager.publish_event(
                event_type="ORDER_STATUS_CHANGED",
                data=order_payload,
                target_kitchen_id=order.kitchen_id,
            )
            ws_manager.publish_event(
                event_type="ORDER_STATUS_CHANGED",
                data=order_payload,
                target_role="ADMIN",
            )
        except Exception as ws_err:
            logger.warning(f"Error publishing real-time transition_order_status event: {ws_err}")

        return order

    @staticmethod
    def list_menu_items(db: Session, user: User) -> List[MenuItem]:
        kitchen = KitchenService._get_kitchen_profile(db, user)
        return db.query(MenuItem).filter(MenuItem.kitchen_id == kitchen.id).order_by(MenuItem.name.asc()).all()

    @staticmethod
    def create_menu_item(db: Session, user: User, req: MenuItemCreate) -> MenuItem:
        kitchen = KitchenService._get_kitchen_profile(db, user)
        item = MenuItem(
            kitchen_id=kitchen.id, meal_id=req.meal_id, name=req.name,
            description=req.description, category=req.category, cuisine=req.cuisine,
            price=req.price, is_available=req.is_available, is_veg=req.is_veg, image_url=req.image_url,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def update_menu_item(db: Session, user: User, item_id: str, req: MenuItemUpdate) -> MenuItem:
        kitchen = KitchenService._get_kitchen_profile(db, user)
        item = db.query(MenuItem).filter(MenuItem.id == item_id, MenuItem.kitchen_id == kitchen.id).first()
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found.")
        for field, value in req.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
        item.updated_at = _utc_now()
        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def delete_menu_item(db: Session, user: User, item_id: str) -> None:
        kitchen = KitchenService._get_kitchen_profile(db, user)
        item = db.query(MenuItem).filter(MenuItem.id == item_id, MenuItem.kitchen_id == kitchen.id).first()
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found.")
        db.delete(item)
        db.commit()

    @staticmethod
    def upload_menu_item_image_file(
        db: Session,
        user: User,
        item_id: str,
        file_content: bytes,
        filename: str,
        content_type: Optional[str] = None
    ) -> MenuItem:
        """Store uploaded image file on disk and set manual image for menu item."""
        kitchen = KitchenService._get_kitchen_profile(db, user)
        item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found.")
        if item.kitchen_id != kitchen.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to modify this menu item.")

        from backend.app.services.image_service import MenuImageService
        saved_url = MenuImageService.validate_and_save_upload_file(file_content, filename, content_type, item_id)

        item.manual_image_url = saved_url
        item.image_url = saved_url
        item.image_source = "MANUAL"
        item.updated_at = _utc_now()
        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def upload_menu_item_image(db: Session, user: User, item_id: str, image_url: str) -> MenuItem:
        """Set manual image for a menu item from URL or relative path. Manual image always takes priority."""
        kitchen = KitchenService._get_kitchen_profile(db, user)
        item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found.")
        if item.kitchen_id != kitchen.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to modify this menu item.")

        from backend.app.services.image_service import MenuImageService
        # If it's a remote URL (http/https), safely download and persist it
        if image_url.strip().lower().startswith(("http://", "https://")):
            saved_url = MenuImageService.download_and_save_remote_image(image_url.strip(), item_id)
        elif image_url.strip().startswith("/uploads/"):
            saved_url = image_url.strip()
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid image URL. Must be an HTTP/HTTPS URL or an existing upload path."
            )

        item.manual_image_url = saved_url
        item.image_url = saved_url
        item.image_source = "MANUAL"
        item.updated_at = _utc_now()
        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def remove_menu_item_image(db: Session, user: User, item_id: str) -> MenuItem:
        """Remove menu item image."""
        kitchen = KitchenService._get_kitchen_profile(db, user)
        item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found.")
        if item.kitchen_id != kitchen.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to modify this menu item.")

        item.manual_image_url = None
        item.image_source = "MANUAL"
        item.image_url = None
        item.updated_at = _utc_now()
        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def set_recipe_ingredient(db: Session, user: User, item_id: str, req: RecipeLinkRequest) -> MenuItemIngredient:
        kitchen = KitchenService._get_kitchen_profile(db, user)
        item = db.query(MenuItem).filter(MenuItem.id == item_id, MenuItem.kitchen_id == kitchen.id).first()
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found.")
        ingredient = KitchenService._assert_kitchen_ingredient(db, kitchen.id, req.ingredient_id)

        req_qty = float(req.quantity_required)
        if req.unit and req.unit.strip().lower() != ingredient.unit.strip().lower():
            try:
                from backend.app.core.unit_converter import convert_quantity
                req_qty = convert_quantity(req.quantity_required, req.unit, ingredient.unit)
            except ValueError as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        existing = db.query(MenuItemIngredient).filter(
            MenuItemIngredient.menu_item_id == item_id, MenuItemIngredient.ingredient_id == req.ingredient_id
        ).first()
        if existing:
            existing.quantity_required = req_qty
            existing.unit = ingredient.unit
            db.commit()
            db.refresh(existing)
            return existing

        link = MenuItemIngredient(menu_item_id=item_id, ingredient_id=req.ingredient_id, quantity_required=req_qty, unit=ingredient.unit)
        db.add(link)
        db.commit()
        db.refresh(link)
        return link

    @staticmethod
    def remove_recipe_ingredient(db: Session, user: User, item_id: str, ingredient_id: str) -> None:
        kitchen = KitchenService._get_kitchen_profile(db, user)
        item = db.query(MenuItem).filter(MenuItem.id == item_id, MenuItem.kitchen_id == kitchen.id).first()
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found.")
        link = db.query(MenuItemIngredient).filter(
            MenuItemIngredient.menu_item_id == item_id, MenuItemIngredient.ingredient_id == ingredient_id
        ).first()
        if link:
            db.delete(link)
            db.commit()

    @staticmethod
    def list_ingredients(db: Session, user: User) -> List[Ingredient]:
        kitchen = KitchenService._get_kitchen_profile(db, user)
        items = db.query(Ingredient).filter(Ingredient.kitchen_id == kitchen.id).order_by(Ingredient.name.asc()).all()
        for ing in items:
            val = KitchenService.get_ingredient_valuation(db, kitchen.id, ing.id, ing.current_stock)
            setattr(ing, "unit_cost", val["unit_cost"])
            setattr(ing, "stock_value", val["stock_value"])
            setattr(ing, "cost_available", val["cost_available"])
        return items

    @staticmethod
    def create_ingredient(db: Session, user: User, req: IngredientCreate) -> Ingredient:
        if req.unit_cost is not None and req.unit_cost < 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unit cost cannot be negative.")

        kitchen = KitchenService._get_kitchen_profile(db, user)
        existing = db.query(Ingredient).filter(Ingredient.kitchen_id == kitchen.id, Ingredient.name == req.name).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Ingredient '{req.name}' already exists.")

        ingredient = Ingredient(
            kitchen_id=kitchen.id, name=req.name, unit=req.unit,
            current_stock=req.initial_stock, minimum_stock_threshold=req.minimum_stock_threshold,
            reorder_quantity=req.reorder_quantity,
            unit_cost=round(float(req.unit_cost), 2) if req.unit_cost is not None else None,
        )
        db.add(ingredient)
        db.flush()

        inv_record = Inventory(
            kitchen_id=kitchen.id, ingredient_id=ingredient.id,
            quantity=req.initial_stock, unit=req.unit,
            status=InventoryStatus.AVAILABLE if req.initial_stock > req.minimum_stock_threshold else InventoryStatus.LOW_STOCK,
        )
        db.add(inv_record)

        if req.initial_stock > 0:
            db.add(InventoryTransaction(
                kitchen_id=kitchen.id, ingredient_id=ingredient.id,
                transaction_type=InventoryTransactionType.INWARD, quantity=req.initial_stock,
                balance_after=req.initial_stock, reason="Initial stock entry",
            ))

            # Record initial purchase cost if entered by owner
            if req.initial_cost is not None and req.initial_cost > 0:
                unit_cost_val = round(float(req.initial_cost) / float(req.initial_stock), 4)
                db.add(Purchase(
                    kitchen_id=kitchen.id,
                    ingredient_id=ingredient.id,
                    supplier_name=req.supplier_name or "Initial Stock",
                    quantity=req.initial_stock,
                    unit=req.unit,
                    unit_cost=round(unit_cost_val, 2),
                    total_cost=round(float(req.initial_cost), 2),
                    purchase_date=_utc_now(),
                    created_at=_utc_now(),
                ))

        db.commit()
        db.refresh(ingredient)

        val = KitchenService.get_ingredient_valuation(db, kitchen.id, ingredient.id, ingredient.current_stock)
        setattr(ingredient, "unit_cost", val["unit_cost"])
        setattr(ingredient, "stock_value", val["stock_value"])
        setattr(ingredient, "cost_available", val["cost_available"])
        return ingredient

    @staticmethod
    def update_ingredient(db: Session, user: User, ingredient_id: str, req: IngredientUpdate) -> Ingredient:
        if req.unit_cost is not None and req.unit_cost < 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unit cost cannot be negative.")

        kitchen = KitchenService._get_kitchen_profile(db, user)
        ingredient = KitchenService._assert_kitchen_ingredient(db, kitchen.id, ingredient_id)
        for field, value in req.model_dump(exclude_unset=True).items():
            if field == "unit_cost" and value is not None:
                setattr(ingredient, field, round(float(value), 2))
            else:
                setattr(ingredient, field, value)
        ingredient.updated_at = _utc_now()
        db.commit()
        db.refresh(ingredient)

        val = KitchenService.get_ingredient_valuation(db, kitchen.id, ingredient.id, ingredient.current_stock)
        setattr(ingredient, "unit_cost", val["unit_cost"])
        setattr(ingredient, "stock_value", val["stock_value"])
        setattr(ingredient, "cost_available", val["cost_available"])
        return ingredient

    @staticmethod
    def delete_ingredient(db: Session, user: User, ingredient_id: str) -> None:
        kitchen = KitchenService._get_kitchen_profile(db, user)
        ingredient = KitchenService._assert_kitchen_ingredient(db, kitchen.id, ingredient_id)
        usage = db.query(MenuItemIngredient).filter(MenuItemIngredient.ingredient_id == ingredient_id).count()
        if usage > 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Ingredient used in {usage} recipe(s). Remove links first.")
        db.delete(ingredient)
        db.commit()

    @staticmethod
    def get_ingredient_valuation(
        db: Session,
        kitchen_id: str,
        ingredient_id: str,
        current_stock: Optional[float] = None,
    ) -> dict:
        """
        Calculates inventory valuation using saved unit cost or the Weighted-Average Cost (WAC) method.
        When a saved unit cost exists on the ingredient, it uses:
            Stock Value = Current Stock * Unit Cost
        Otherwise, only genuine purchases with unit_cost > 0.0 and quantity > 0.0 are considered.
        """
        ing = db.query(Ingredient).filter(
            Ingredient.id == ingredient_id,
            Ingredient.kitchen_id == kitchen_id,
        ).first()
        if not ing:
            ing = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()

        if current_stock is None:
            current_stock = float(ing.current_stock) if ing else 0.0
        else:
            current_stock = float(current_stock)

        # 1. If ingredient has a genuine saved unit cost (>= 0), use saved unit cost directly
        if ing and ing.unit_cost is not None and ing.unit_cost >= 0:
            saved_unit_cost = float(ing.unit_cost)
            stock_val = round(max(0.0, current_stock) * saved_unit_cost, 2)
            return {
                "unit_cost": round(saved_unit_cost, 2),
                "unit_cost_precise": saved_unit_cost,
                "cost_available": True,
                "stock_value": stock_val,
                "valuation_method": "SAVED_UNIT_COST",
                "total_purchased_qty": 0.0,
                "total_purchase_cost": 0.0,
                "purchases_count": 0,
            }

        # 2. Otherwise calculate inventory valuation using the Weighted-Average Cost (WAC) method
        purchases = db.query(Purchase).filter(
            Purchase.kitchen_id == kitchen_id,
            Purchase.ingredient_id == ingredient_id,
            Purchase.unit_cost > 0.0,
            Purchase.quantity > 0.0,
        ).order_by(Purchase.purchase_date.asc(), Purchase.created_at.asc()).all()

        if not purchases:
            return {
                "unit_cost": None,
                "cost_available": False,
                "stock_value": None,
                "valuation_method": "WEIGHTED_AVERAGE",
                "total_purchased_qty": 0.0,
                "total_purchase_cost": 0.0,
                "purchases_count": 0,
            }

        total_qty = 0.0
        total_cost = 0.0
        for p in purchases:
            qty = float(p.quantity)
            c = float(p.total_cost) if p.total_cost and p.total_cost > 0 else float(p.unit_cost) * qty
            total_qty += qty
            total_cost += c

        if total_qty <= 0 or total_cost <= 0:
            return {
                "unit_cost": None,
                "cost_available": False,
                "stock_value": None,
                "valuation_method": "WEIGHTED_AVERAGE",
                "total_purchased_qty": 0.0,
                "total_purchase_cost": 0.0,
                "purchases_count": len(purchases),
            }

        avg_unit_cost = total_cost / total_qty
        stock_val = round(max(0.0, current_stock) * avg_unit_cost, 2)
        return {
            "unit_cost": round(avg_unit_cost, 2),
            "unit_cost_precise": avg_unit_cost,
            "cost_available": True,
            "stock_value": stock_val,
            "valuation_method": "WEIGHTED_AVERAGE",
            "total_purchased_qty": round(total_qty, 4),
            "total_purchase_cost": round(total_cost, 2),
            "purchases_count": len(purchases),
        }

    @staticmethod
    def _get_ingredient_unit_cost(db: Session, kitchen_id: str, ingredient_id: str) -> Optional[float]:
        """Retrieve weighted-average unit cost (> 0.0) for an ingredient in this kitchen."""
        val = KitchenService.get_ingredient_valuation(db, kitchen_id, ingredient_id)
        return val["unit_cost"] if val["cost_available"] else None

    @staticmethod
    def restock_ingredient(db: Session, user: User, req: InventoryRestockRequest) -> Ingredient:
        if req.quantity <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Restock quantity must be greater than 0.")
        if req.unit_cost is not None and req.unit_cost < 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unit cost cannot be negative.")
        if req.total_price is not None and req.total_price < 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Total purchase price cannot be negative.")
        if req.total_cost is not None and req.total_cost < 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Total purchase price cannot be negative.")

        kitchen = KitchenService._get_kitchen_profile(db, user)
        ingredient = KitchenService._assert_kitchen_ingredient(db, kitchen.id, req.ingredient_id)

        # Unit conversion if purchase_unit is provided and differs from ingredient.unit
        base_qty = float(req.quantity)
        if req.purchase_unit and req.purchase_unit.strip().lower() != ingredient.unit.strip().lower():
            try:
                from backend.app.core.unit_converter import convert_quantity
                base_qty = convert_quantity(req.quantity, req.purchase_unit, ingredient.unit)
            except ValueError as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        # Standardize movement type
        raw_m = (req.movement_type or "PURCHASE").upper().strip()
        if "RETURN" in raw_m:
            txn_type = InventoryTransactionType.RETURN
            m_label = "Return"
        elif "TRANSFER" in raw_m:
            txn_type = InventoryTransactionType.TRANSFER_IN
            m_label = "Transfer In"
        elif "ADJUSTMENT" in raw_m:
            txn_type = InventoryTransactionType.ADJUSTMENT
            m_label = "Adjustment"
        else:
            txn_type = InventoryTransactionType.INWARD
            m_label = "Purchase / Restock"

        # Determine price & unit cost
        # total_price / total_cost takes precedence, or unit_cost
        effective_total_cost: Optional[float] = None
        effective_unit_cost: Optional[float] = None

        req_total = req.total_price if req.total_price is not None else req.total_cost
        if req_total is not None and req_total > 0:
            effective_total_cost = float(req_total)
            effective_unit_cost = round(effective_total_cost / base_qty, 4)
        elif req.unit_cost is not None and req.unit_cost > 0:
            # unit_cost entered: calculate total cost and unit cost in base unit
            effective_total_cost = round(float(req.unit_cost) * float(req.quantity), 2)
            effective_unit_cost = round(effective_total_cost / base_qty, 4)

        reason_parts = [f"Restock ({m_label})"]
        if req.purchase_unit and req.purchase_unit.strip().lower() != ingredient.unit.strip().lower():
            reason_parts.append(f"Added {req.quantity} {req.purchase_unit} ({base_qty:.2f} {ingredient.unit})")
        if effective_total_cost is not None and effective_total_cost > 0:
            reason_parts.append(f"Total: ₹{effective_total_cost:.2f}")
        if req.reason:
            reason_parts.append(req.reason)
        if req.notes:
            reason_parts.append(req.notes)
        txn_reason = " - ".join(reason_parts)

        try:
            # 1. Update current stock (decimal supported)
            ingredient.current_stock += base_qty
            ingredient.updated_at = _utc_now()

            # 2. Update or create inventory record
            inv_record = db.query(Inventory).filter(
                Inventory.kitchen_id == kitchen.id, Inventory.ingredient_id == req.ingredient_id
            ).first()
            if inv_record:
                inv_record.quantity = ingredient.current_stock
                inv_record.status = (
                    InventoryStatus.AVAILABLE if ingredient.current_stock > ingredient.minimum_stock_threshold else InventoryStatus.LOW_STOCK
                )
                if req.batch_number:
                    inv_record.batch_number = req.batch_number
                if req.expiry_date:
                    inv_record.expiry_date = req.expiry_date
                inv_record.last_updated = _utc_now()
            else:
                inv_record = Inventory(
                    kitchen_id=kitchen.id,
                    ingredient_id=req.ingredient_id,
                    batch_number=req.batch_number,
                    expiry_date=req.expiry_date,
                    quantity=ingredient.current_stock,
                    unit=ingredient.unit,
                    status=InventoryStatus.AVAILABLE if ingredient.current_stock > ingredient.minimum_stock_threshold else InventoryStatus.LOW_STOCK,
                )
                db.add(inv_record)

            # 3. Add inventory transaction ledger entry
            db.add(InventoryTransaction(
                kitchen_id=kitchen.id,
                ingredient_id=req.ingredient_id,
                transaction_type=txn_type,
                quantity=base_qty,
                balance_after=ingredient.current_stock,
                reason=txn_reason,
            ))

            # 4. Add purchase record ONLY if actual cost was provided (> 0.0)
            if effective_unit_cost is not None and effective_unit_cost > 0:
                supplier_val = req.supplier_name or ("Supplier Purchase" if "PURCHASE" in raw_m else m_label)
                p_date = req.purchase_date if req.purchase_date else _utc_now()
                db.add(Purchase(
                    kitchen_id=kitchen.id,
                    ingredient_id=req.ingredient_id,
                    supplier_name=supplier_val,
                    invoice_number=req.invoice_number,
                    quantity=base_qty,
                    unit=ingredient.unit,
                    unit_cost=round(effective_unit_cost, 2),
                    total_cost=round(effective_total_cost, 2),
                    purchase_date=p_date,
                    created_at=p_date,
                ))

            db.commit()
            db.refresh(ingredient)

            val = KitchenService.get_ingredient_valuation(db, kitchen.id, ingredient.id, ingredient.current_stock)
            setattr(ingredient, "stock_value", val["stock_value"])
            setattr(ingredient, "cost_available", val["cost_available"])

            try:
                from backend.app.websockets.connection_manager import ws_manager
                inv_payload = {
                    "kitchen_id": kitchen.id,
                    "ingredient_id": ingredient.id,
                    "ingredient_name": ingredient.name,
                    "current_stock": float(ingredient.current_stock),
                    "unit": ingredient.unit,
                    "reason": "RESTOCK",
                }
                ws_manager.publish_event(
                    event_type="INVENTORY_UPDATED",
                    data=inv_payload,
                    target_kitchen_id=kitchen.id,
                )
                ws_manager.publish_event(
                    event_type="INVENTORY_UPDATED",
                    data=inv_payload,
                    target_role="ADMIN",
                )
            except Exception as ws_err:
                logger.warning(f"Error publishing restock real-time event: {ws_err}")

            return ingredient
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def _deduct_inventory(
        db: Session,
        kitchen_id: str,
        ingredient_id: str,
        quantity: float,
        order_id: Optional[str],
        reason: str,
        transaction_type: InventoryTransactionType = InventoryTransactionType.OUTWARD_ORDER,
    ) -> None:
        ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id, Ingredient.kitchen_id == kitchen_id).first()
        if not ingredient:
            return
        ingredient.current_stock = max(0.0, ingredient.current_stock - quantity)
        ingredient.updated_at = _utc_now()

        inv_record = db.query(Inventory).filter(Inventory.kitchen_id == kitchen_id, Inventory.ingredient_id == ingredient_id).first()
        if inv_record:
            inv_record.quantity = ingredient.current_stock
            inv_record.status = (
                InventoryStatus.LOW_STOCK if ingredient.current_stock <= ingredient.minimum_stock_threshold else InventoryStatus.AVAILABLE
            )
            inv_record.last_updated = _utc_now()
        else:
            inv_record = Inventory(
                kitchen_id=kitchen_id,
                ingredient_id=ingredient_id,
                quantity=ingredient.current_stock,
                unit=ingredient.unit,
                status=InventoryStatus.LOW_STOCK if ingredient.current_stock <= ingredient.minimum_stock_threshold else InventoryStatus.AVAILABLE,
            )
            db.add(inv_record)

        db.add(InventoryTransaction(
            kitchen_id=kitchen_id,
            ingredient_id=ingredient_id,
            transaction_type=transaction_type,
            quantity=-quantity,
            balance_after=ingredient.current_stock,
            reference_order_id=order_id,
            reason=reason,
        ))

        # Check if low stock threshold crossed
        if ingredient.current_stock <= ingredient.minimum_stock_threshold:
            kitchen = db.query(KitchenProfile).filter(KitchenProfile.id == kitchen_id).first()
            if kitchen:
                db.add(Notification(
                    user_id=kitchen.user_id,
                    title=f"Low Stock: {ingredient.name}",
                    message=f"{ingredient.name}: {ingredient.current_stock:.1f} {ingredient.unit} remaining (threshold: {ingredient.minimum_stock_threshold:.1f}). Please restock.",
                    event_type="LOW_STOCK",
                ))
                from backend.app.services.notification_service import NotificationService
                NotificationService.notify_admins(
                    db=db,
                    event_type="LOW_STOCK",
                    title=f"Low Stock: {ingredient.name}",
                    message=f"{kitchen.kitchen_name} stock for {ingredient.name} is at {ingredient.current_stock:.1f} {ingredient.unit} (threshold: {ingredient.minimum_stock_threshold:.1f}).",
                    metadata={"entity_type": "inventory", "entity_id": ingredient.id, "kitchen_id": kitchen.id, "link": "/admin/inventory"}
                )
                try:
                    if kitchen.user and kitchen.user.email:
                        email_service.send_low_stock_email_sync(
                            to_email=kitchen.user.email,
                            kitchen_name=kitchen.kitchen_name,
                            ingredient_name=ingredient.name,
                            current_stock=ingredient.current_stock,
                            unit=ingredient.unit,
                            threshold=ingredient.minimum_stock_threshold,
                        )
                except Exception as e:
                    logger.warning(f"Failed to send low stock alert email to kitchen owner {kitchen.user.email if kitchen.user else ''}: {e}")

    @staticmethod
    def get_inventory_transactions(db: Session, user: User, ingredient_id: Optional[str] = None, limit: int = 100) -> List[InventoryTransaction]:
        kitchen = KitchenService._get_kitchen_profile(db, user)
        q = db.query(InventoryTransaction).filter(InventoryTransaction.kitchen_id == kitchen.id)
        if ingredient_id:
            q = q.filter(InventoryTransaction.ingredient_id == ingredient_id)
        return q.order_by(InventoryTransaction.created_at.desc()).limit(limit).all()

    @staticmethod
    def calculate_forecasted_ingredient_usage(db: Session, kitchen_id: str) -> dict[str, float]:
        """
        Calculate expected ingredient usage from forecasted menu item demand and recipe links.
        Reuses the exact operational forecasting logic:
          - Real orders for the kitchen
          - History span
          - Daily portion velocity per menu item
          - Recipe ingredient quantities per portion
        """
        real_orders = db.query(Order).filter(Order.kitchen_id == kitchen_id).all()
        if not real_orders:
            return {}

        orders_by_day = set(o.created_at.strftime("%Y-%m-%d") for o in real_orders if o.created_at)
        distinct_days = len(orders_by_day)

        dates = [o.created_at for o in real_orders if o.created_at]
        earliest_date = min(dates) if dates else None
        now_utc = datetime.now(timezone.utc)
        if earliest_date:
            first_tz = earliest_date if earliest_date.tzinfo else earliest_date.replace(tzinfo=timezone.utc)
            history_days = max(distinct_days, max(1, (now_utc - first_tz).days))
        else:
            history_days = max(1, distinct_days)

        effective_days = max(1, history_days)

        item_sales: dict[str, int] = {}
        for o in real_orders:
            for it in o.items:
                if it.menu_item_id:
                    item_sales[it.menu_item_id] = item_sales.get(it.menu_item_id, 0) + it.quantity

        menu_items = db.query(MenuItem).filter(MenuItem.kitchen_id == kitchen_id).all()
        ingredient_usage: dict[str, float] = {}

        for m in menu_items:
            units_sold = item_sales.get(m.id, 0)
            daily_velocity = units_sold / effective_days
            daily_predicted_portions = max(1, round(daily_velocity)) if units_sold > 0 else 0

            for recipe_link in m.ingredients_recipe:
                ing = recipe_link.ingredient
                if ing:
                    qty = round(daily_predicted_portions * recipe_link.quantity_required, 3)
                    ingredient_usage[ing.id] = round(ingredient_usage.get(ing.id, 0.0) + qty, 3)

        return ingredient_usage

    @staticmethod
    def get_restock_recommendations(db: Session, user: User) -> List[RestockingRecommendation]:
        """
        Forecast-aware Restocking Engine:
        Evaluates:
          FORECASTED MENU DEMAND
          -> RECIPE INGREDIENT REQUIREMENT
          -> CURRENT INVENTORY
          -> PROJECTED STOCK AFTER FORECAST
          -> COMPARE WITH MINIMUM THRESHOLD
          -> RESTOCK REQUIRED / SHORTAGE / SUFFICIENT

        restock_needed = max(0, forecasted_usage + minimum_threshold - current_stock)
        """
        kitchen = KitchenService._get_kitchen_profile(db, user)
        all_ingredients = db.query(Ingredient).filter(
            Ingredient.kitchen_id == kitchen.id
        ).order_by(Ingredient.name).all()

        usage_map = KitchenService.calculate_forecasted_ingredient_usage(db, kitchen.id)

        recommendations = []
        for ing in all_ingredients:
            current_stock = round(float(ing.current_stock), 2)
            min_thresh = round(float(ing.minimum_stock_threshold), 2)
            expected_usage = round(float(usage_map.get(ing.id, 0.0)), 2)
            projected_stock = round(current_stock - expected_usage, 2)

            # Calculation: restock_needed = max(0, expected_usage + minimum_threshold - current_stock)
            restock_needed = max(0.0, round(expected_usage + min_thresh - current_stock, 2))

            # Case classification:
            # CASE 3: Current stock < forecasted usage -> SHORTAGE
            if current_stock < expected_usage:
                status_str = "SHORTAGE"
                urgency = "CRITICAL"
                short_by = round(expected_usage - current_stock, 2)
            # CASE 1: Projected stock after forecast < minimum threshold -> RESTOCK REQUIRED
            elif projected_stock < min_thresh:
                status_str = "RESTOCK REQUIRED"
                urgency = "HIGH" if current_stock <= min_thresh else "MEDIUM"
                short_by = round(min_thresh - projected_stock, 2)
            # CASE 2: Projected stock >= minimum threshold -> SUFFICIENT
            else:
                status_str = "SUFFICIENT"
                urgency = "NORMAL"
                short_by = 0.0

            cfg_reorder = float(ing.reorder_quantity) if ing.reorder_quantity and ing.reorder_quantity > 0 else 0.0
            if restock_needed > 0:
                recommended_qty = max(cfg_reorder, restock_needed)
            else:
                recommended_qty = cfg_reorder

            inv_status = InventoryStatus.LOW_STOCK if status_str != "SUFFICIENT" else InventoryStatus.AVAILABLE

            val = KitchenService.get_ingredient_valuation(db, kitchen.id, ing.id, current_stock)
            rec_unit_cost = val["unit_cost"] if val["cost_available"] else None
            rec_est_cost = round(recommended_qty * rec_unit_cost, 2) if rec_unit_cost is not None else None

            recommendations.append(RestockingRecommendation(
                ingredient_id=ing.id,
                ingredient_name=ing.name,
                unit=ing.unit,
                current_stock=current_stock,
                expected_usage=expected_usage,
                projected_stock=projected_stock,
                minimum_threshold=min_thresh,
                minimum_stock_threshold=min_thresh,
                short_by=short_by,
                restock_needed=restock_needed,
                recommended_reorder_qty=recommended_qty,
                recommended_reorder_quantity=recommended_qty,
                status=inv_status,
                forecast_status=status_str,
                urgency_level=urgency,
                urgency=urgency,
                unit_cost=rec_unit_cost,
                estimated_cost=rec_est_cost,
                cost_available=val["cost_available"],
            ))

        def sort_key(r):
            order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "NORMAL": 3}
            return (order.get(r.urgency_level, 9), r.ingredient_name)

        recommendations.sort(key=sort_key)
        return recommendations

    @staticmethod
    def record_waste(db: Session, user: User, req: WasteRecordCreate) -> WasteRecord:
        if req.quantity <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Waste quantity must be greater than 0.")

        kitchen = KitchenService._get_kitchen_profile(db, user)
        ingredient = KitchenService._assert_kitchen_ingredient(db, kitchen.id, req.ingredient_id)

        if req.quantity > ingredient.current_stock:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot waste more than available stock. Current stock is {round(ingredient.current_stock, 3)} {ingredient.unit}."
            )

        try:
            # 1. Deduct current stock atomically
            ingredient.current_stock = max(0.0, ingredient.current_stock - req.quantity)
            ingredient.updated_at = _utc_now()

            # 2. Update inventory record
            inv_record = db.query(Inventory).filter(
                Inventory.kitchen_id == kitchen.id, Inventory.ingredient_id == req.ingredient_id
            ).first()
            if inv_record:
                inv_record.quantity = ingredient.current_stock
                inv_record.status = (
                    InventoryStatus.LOW_STOCK if ingredient.current_stock <= ingredient.minimum_stock_threshold else InventoryStatus.AVAILABLE
                )
                inv_record.last_updated = _utc_now()
            else:
                inv_record = Inventory(
                    kitchen_id=kitchen.id,
                    ingredient_id=req.ingredient_id,
                    quantity=ingredient.current_stock,
                    unit=ingredient.unit,
                    status=InventoryStatus.LOW_STOCK if ingredient.current_stock <= ingredient.minimum_stock_threshold else InventoryStatus.AVAILABLE,
                )
                db.add(inv_record)

            # 3. Add inventory transaction ledger entry
            waste_notes = f" - {req.notes}" if getattr(req, "notes", None) else ""
            db.add(InventoryTransaction(
                kitchen_id=kitchen.id,
                ingredient_id=req.ingredient_id,
                transaction_type=InventoryTransactionType.WASTE,
                quantity=-req.quantity,
                balance_after=ingredient.current_stock,
                reference_order_id=None,
                reason=f"Waste: {req.reason}{waste_notes}",
            ))

            # 4. Resolve unit cost: wasted_quantity * actual_unit_cost
            unit_cost = KitchenService._get_ingredient_unit_cost(db, kitchen.id, req.ingredient_id)
            est_cost = round(req.quantity * unit_cost, 2) if unit_cost is not None else None

            waste = WasteRecord(
                kitchen_id=kitchen.id,
                ingredient_id=req.ingredient_id,
                quantity=req.quantity,
                unit=ingredient.unit,
                reason=req.reason,
                recorded_by=user.full_name or user.email,
                estimated_cost=est_cost,
                portions_wasted=1.0,
                source_event="MANUAL",
            )
            db.add(waste)
            db.commit()
            db.refresh(waste)

            try:
                from backend.app.websockets.connection_manager import ws_manager
                waste_payload = {
                    "waste_id": waste.id,
                    "kitchen_id": kitchen.id,
                    "ingredient_id": waste.ingredient_id,
                    "quantity": float(waste.quantity),
                    "unit": waste.unit,
                    "reason": waste.reason,
                    "estimated_cost": float(waste.estimated_cost) if waste.estimated_cost else 0.0,
                    "recorded_by": waste.recorded_by,
                    "created_at": waste.created_at.isoformat() if waste.created_at else None,
                }
                ws_manager.publish_event(
                    event_type="WASTE_RECORD_CREATED",
                    data=waste_payload,
                    target_kitchen_id=kitchen.id,
                )
                ws_manager.publish_event(
                    event_type="WASTE_RECORD_CREATED",
                    data=waste_payload,
                    target_role="ADMIN",
                )
                # Also signal inventory update
                ws_manager.publish_event(
                    event_type="INVENTORY_UPDATED",
                    data={"kitchen_id": kitchen.id, "ingredient_id": waste.ingredient_id, "reason": "WASTE_DEDUCTION"},
                    target_kitchen_id=kitchen.id,
                )
                ws_manager.publish_event(
                    event_type="INVENTORY_UPDATED",
                    data={"kitchen_id": kitchen.id, "ingredient_id": waste.ingredient_id, "reason": "WASTE_DEDUCTION"},
                    target_role="ADMIN",
                )
            except Exception as ws_err:
                logger.warning(f"Error publishing waste real-time event: {ws_err}")

            return waste
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def get_waste_records(db: Session, user: User, limit: int = 100) -> List[WasteRecord]:
        kitchen = KitchenService._get_kitchen_profile(db, user)
        return db.query(WasteRecord).filter(WasteRecord.kitchen_id == kitchen.id).order_by(WasteRecord.created_at.desc()).limit(limit).all()

    @staticmethod
    def get_waste_analytics(
        db: Session,
        user: User,
        year: Optional[int] = None,
        month: Optional[int] = None
    ) -> WasteAnalyticsResponse:
        kitchen = KitchenService._get_kitchen_profile(db, user)
        now = datetime.now(timezone.utc)
        target_year = year or now.year
        target_month = month or now.month

        # Period start and end (UTC)
        start_of_period = datetime(target_year, target_month, 1, 0, 0, 0, tzinfo=timezone.utc)
        last_day = calendar.monthrange(target_year, target_month)[1]
        end_of_period = datetime(target_year, target_month, last_day, 23, 59, 59, tzinfo=timezone.utc)
        period_label = f"{calendar.month_name[target_month]} {target_year}"

        # 1. Fetch real WasteRecords for this kitchen in this period
        records = db.query(WasteRecord).filter(
            WasteRecord.kitchen_id == kitchen.id,
            WasteRecord.created_at >= start_of_period,
            WasteRecord.created_at <= end_of_period,
        ).all()

        # Cache resolved costs for records where estimated_cost is missing or 0.0 but unit cost exists
        resolved_record_costs = {}
        for r in records:
            c = r.estimated_cost
            if (c is None or c == 0.0) and r.ingredient_id:
                u_cost = KitchenService._get_ingredient_unit_cost(db, kitchen.id, r.ingredient_id)
                if u_cost is not None and u_cost > 0:
                    c = round(r.quantity * u_cost, 2)
                else:
                    c = None
            resolved_record_costs[r.id] = c

        total_cost = round(sum(c for c in resolved_record_costs.values() if c is not None), 2)
        wasted_order_ids = set(r.order_id for r in records if r.order_id)
        wasted_orders_count = len(wasted_order_ids)

        # Unique portions wasted (avoid double-counting across multi-ingredient recipe records)
        seen_portions_keys = set()
        total_wasted_portions = 0.0
        for r in records:
            if r.order_id:
                key = (r.order_id, r.menu_item_name or r.menu_item_id or r.id)
                if key not in seen_portions_keys:
                    seen_portions_keys.add(key)
                    total_wasted_portions += float(r.portions_wasted or 1.0)
            else:
                total_wasted_portions += float(r.portions_wasted or 1.0)
        total_wasted_portions = round(total_wasted_portions, 1)

        # 2. Prepared food portions in this period
        prepared_orders = db.query(Order).filter(
            Order.kitchen_id == kitchen.id,
            Order.created_at >= start_of_period,
            Order.created_at <= end_of_period,
            (
                Order.status.in_([
                    OrderStatus.PREPARING,
                    OrderStatus.READY,
                    OrderStatus.OUT_FOR_DELIVERY,
                    OrderStatus.DELIVERED
                ])
                | (Order.id.in_(wasted_order_ids))
            )
        ).all()

        prepared_food_portions = 0.0
        for ord_obj in prepared_orders:
            for item in ord_obj.items:
                prepared_food_portions += float(item.quantity)

        if prepared_food_portions < total_wasted_portions:
            prepared_food_portions = total_wasted_portions

        if prepared_food_portions > 0:
            wastage_rate = round((total_wasted_portions / prepared_food_portions) * 100.0, 1)
        else:
            wastage_rate = 0.0

        # 3. Wastage by Reason
        reason_map: dict[str, dict] = {}
        for r in records:
            raw_reason = r.reason or "Other"
            if "CUSTOMER_CANCELLED_AFTER_PREPARATION" in raw_reason.upper():
                display_reason = "Customer cancelled after preparation"
            elif "CUSTOMER_CANCELLED_AFTER_READY" in raw_reason.upper():
                display_reason = "Customer cancelled after food was ready"
            elif "SPOIL" in raw_reason.upper():
                display_reason = "Spoiled"
            elif "EXPIR" in raw_reason.upper():
                display_reason = "Expired"
            elif "PREPARATION ERROR" in raw_reason.upper() or "ERROR" in raw_reason.upper():
                display_reason = "Preparation error"
            elif "SPILL" in raw_reason.upper():
                display_reason = "Spilled"
            elif "DAMAG" in raw_reason.upper():
                display_reason = "Damaged"
            else:
                display_reason = raw_reason

            if display_reason not in reason_map:
                reason_map[display_reason] = {"count": 0, "total_cost": 0.0, "has_any_cost": False, "total_quantity": 0.0}
            reason_map[display_reason]["count"] += 1
            reason_map[display_reason]["total_quantity"] += (r.quantity or 0.0)

            c = resolved_record_costs.get(r.id)
            if c is not None:
                reason_map[display_reason]["total_cost"] += c
                reason_map[display_reason]["has_any_cost"] = True

        by_reason = [
            WasteByReasonItem(
                reason=k,
                count=v["count"],
                total_cost=round(v["total_cost"], 2) if v["has_any_cost"] else None,
                cost_available=v["has_any_cost"],
                total_quantity=round(v["total_quantity"], 2)
            )
            for k, v in sorted(reason_map.items(), key=lambda x: (x[1]["total_cost"] if x[1]["has_any_cost"] else -1), reverse=True)
        ]

        # 4. Wastage by Menu Item (derived from recipe records)
        item_map: dict[str, dict] = {}
        for r in records:
            name = r.menu_item_name
            if not name and r.menu_item_id:
                mi = db.query(MenuItem).filter(MenuItem.id == r.menu_item_id).first()
                name = mi.name if mi else "Unknown Dish"
            if name:
                if name not in item_map:
                    item_map[name] = {"portions": 0.0, "cost": 0.0, "has_cost": False, "seen_orders": set()}
                if r.order_id:
                    if r.order_id not in item_map[name]["seen_orders"]:
                        item_map[name]["seen_orders"].add(r.order_id)
                        item_map[name]["portions"] += (r.portions_wasted or 1.0)
                else:
                    item_map[name]["portions"] += (r.portions_wasted or 1.0)
                c = resolved_record_costs.get(r.id)
                if c is not None:
                    item_map[name]["cost"] += c
                    item_map[name]["has_cost"] = True

        by_menu_item = [
            WasteByMenuItem(
                menu_item_name=k,
                portions_wasted=round(v["portions"], 1),
                estimated_cost=round(v["cost"], 2) if v["has_cost"] else None,
                cost_available=v["has_cost"],
            )
            for k, v in sorted(item_map.items(), key=lambda x: (x[1]["cost"] if x[1]["has_cost"] else -1), reverse=True)
        ]

        # 5. Wastage by Ingredient
        ing_map: dict[str, dict] = {}
        for r in records:
            ing_name = None
            unit_val = r.unit or "kg"
            ing_id = r.ingredient_id
            if r.ingredient:
                ing_name = r.ingredient.name
                unit_val = r.ingredient.unit
            elif ing_id:
                ing_obj = db.query(Ingredient).filter(Ingredient.id == ing_id).first()
                if ing_obj:
                    ing_name = ing_obj.name
                    unit_val = ing_obj.unit
            if ing_name:
                if ing_name not in ing_map:
                    ing_map[ing_name] = {
                        "ingredient_id": ing_id,
                        "quantity": 0.0,
                        "unit": unit_val,
                        "cost": 0.0,
                        "has_any_cost": False,
                    }
                ing_map[ing_name]["quantity"] += (r.quantity or 0.0)
                c = resolved_record_costs.get(r.id)
                if c is not None:
                    ing_map[ing_name]["cost"] += c
                    ing_map[ing_name]["has_any_cost"] = True

        by_ingredient = []
        for k, v in ing_map.items():
            u_cost = None
            if v["ingredient_id"]:
                u_cost = KitchenService._get_ingredient_unit_cost(db, kitchen.id, v["ingredient_id"])
            cost_avail = v["has_any_cost"]
            by_ingredient.append(
                WasteByIngredientItem(
                    ingredient_name=k,
                    quantity=round(v["quantity"], 2),
                    total_quantity=round(v["quantity"], 2),
                    unit=v["unit"],
                    unit_cost=u_cost,
                    estimated_cost=round(v["cost"], 2) if cost_avail else None,
                    cost_available=cost_avail,
                )
            )

        by_ingredient.sort(key=lambda x: (x.estimated_cost if x.cost_available and x.estimated_cost is not None else -1), reverse=True)

        # 6. Monthly Trend (Real DB records over past 6 months)
        monthly_trend = []
        for i in range(5, -1, -1):
            m_date = now - timedelta(days=i * 30)
            m_year = m_date.year
            m_month = m_date.month
            m_start = datetime(m_year, m_month, 1, tzinfo=timezone.utc)
            m_last_day = calendar.monthrange(m_year, m_month)[1]
            m_end = datetime(m_year, m_month, m_last_day, 23, 59, 59, tzinfo=timezone.utc)
            m_records = db.query(WasteRecord).filter(
                WasteRecord.kitchen_id == kitchen.id,
                WasteRecord.created_at >= m_start,
                WasteRecord.created_at <= m_end,
            ).all()

            m_cost = round(sum(mr.estimated_cost or 0.0 for mr in m_records), 2)
            m_portions = 0.0
            seen_m_keys = set()
            for mr in m_records:
                if mr.order_id:
                    key = (mr.order_id, mr.menu_item_name or mr.menu_item_id or mr.id)
                    if key not in seen_m_keys:
                        seen_m_keys.add(key)
                        m_portions += float(mr.portions_wasted or 1.0)
                else:
                    m_portions += float(mr.portions_wasted or 1.0)

            monthly_trend.append(MonthlyWasteTrendItem(
                month=f"{m_year}-{m_month:02d}",
                month_label=f"{calendar.month_abbr[m_month]} {m_year}",
                total_cost=m_cost,
                portions_wasted=round(m_portions, 1),
                count=len(m_records),
            ))

        return WasteAnalyticsResponse(
            period_label=period_label,
            total_cost=total_cost,
            wasted_orders_count=wasted_orders_count,
            total_wasted_portions=total_wasted_portions,
            prepared_food_portions=round(prepared_food_portions, 1),
            wastage_rate=wastage_rate,
            by_reason=by_reason,
            by_menu_item=by_menu_item,
            by_ingredient=by_ingredient,
            monthly_trend=monthly_trend,
        )

    @staticmethod
    def get_delivery_route(db: Session, user: User, order_id: str) -> DeliveryRouteResponse:
        """
        Server-side authorized delivery route between kitchen registered location
        and customer order delivery address snapshot.
        Enforces that kitchen owners can only view routes for orders in their kitchen.
        """
        kitchen = KitchenService._get_kitchen_profile(db, user)
        order = KitchenService._assert_kitchen_order(db, kitchen.id, order_id)

        k_lat = kitchen.latitude
        k_lon = kitchen.longitude
        k_addr = f"{kitchen.address}, {kitchen.city}"

        c_lat = order.delivery_latitude if order.delivery_latitude is not None else (order.delivery_address.latitude if order.delivery_address else None)
        c_lon = order.delivery_longitude if order.delivery_longitude is not None else (order.delivery_address.longitude if order.delivery_address else None)
        c_addr = order.delivery_address_text or (
            f"{order.delivery_address.address_line1}, {order.delivery_address.city} {order.delivery_address.postal_code}"
            if order.delivery_address else "Standard Delivery"
        )
        c_name = order.customer.full_name if order.customer else "Customer"
        c_phone = order.customer.phone_number if order.customer else None

        k_info = DeliveryLocationInfo(
            name=kitchen.kitchen_name,
            address=k_addr,
            latitude=k_lat,
            longitude=k_lon,
            phone=kitchen.phone,
        )
        c_info = DeliveryLocationInfo(
            name=c_name,
            address=c_addr,
            latitude=c_lat,
            longitude=c_lon,
            phone=c_phone,
        )

        is_active = order.status not in [OrderStatus.CANCELLED, OrderStatus.REJECTED]

        if k_lat is None or k_lon is None:
            return DeliveryRouteResponse(
                order_id=order.id,
                order_number=order.order_number,
                order_status=order.status,
                is_active_delivery=is_active,
                kitchen=k_info,
                customer=c_info,
                route_available=False,
                message="Route unavailable: Kitchen location is unavailable.",
            )

        if c_lat is None or c_lon is None:
            return DeliveryRouteResponse(
                order_id=order.id,
                order_number=order.order_number,
                order_status=order.status,
                is_active_delivery=is_active,
                kitchen=k_info,
                customer=c_info,
                route_available=False,
                message="Route unavailable: Customer delivery location is not confirmed.",
            )

        maps_url = f"https://www.google.com/maps/dir/?api=1&origin={k_lat},{k_lon}&destination={c_lat},{c_lon}"

        # Real route query using OSRM with short timeout
        import urllib.request
        import json
        route_url = f"https://router.project-osrm.org/route/v1/driving/{k_lon},{k_lat};{c_lon},{c_lat}?overview=full&geometries=geojson"
        req = urllib.request.Request(route_url, headers={"User-Agent": "CloudKitchen-UnifiedPlatform/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("code") == "Ok" and data.get("routes"):
                    r_data = data["routes"][0]
                    dist_km = round(r_data.get("distance", 0.0) / 1000.0, 2)
                    dur_min = max(1, round(r_data.get("duration", 0.0) / 60.0))
                    raw_coords = r_data.get("geometry", {}).get("coordinates", [])
                    # Convert GeoJSON [lon, lat] to Leaflet [lat, lon]
                    leaflet_coords = [[pt[1], pt[0]] for pt in raw_coords]
                    return DeliveryRouteResponse(
                        order_id=order.id,
                        order_number=order.order_number,
                        order_status=order.status,
                        is_active_delivery=is_active,
                        kitchen=k_info,
                        customer=c_info,
                        distance_km=dist_km,
                        duration_minutes=dur_min,
                        route_coordinates=leaflet_coords,
                        route_available=True,
                        maps_url=maps_url,
                    )
        except Exception as e:
            logger.warning(f"OSRM routing query error for order {order.id}: {e}")

        # If routing failed, timeout, or offline: clearly show Route unavailable
        return DeliveryRouteResponse(
            order_id=order.id,
            order_number=order.order_number,
            order_status=order.status,
            is_active_delivery=is_active,
            kitchen=k_info,
            customer=c_info,
            route_available=False,
            message="Route unavailable",
            maps_url=maps_url,
        )

    @staticmethod
    def update_settings(db: Session, user: User, req: KitchenSettingsUpdate) -> KitchenProfile:
        kitchen = KitchenService._get_kitchen_profile(db, user, require_approved=False)
        update_dict = req.model_dump(exclude_unset=True)
        if update_dict.get("is_open") is True:
            if not kitchen.is_approved:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot open kitchen: Account approval is pending."
                )
            if kitchen.license:
                from backend.app.services.fssai_service import FssaiService
                from backend.app.models.enums import LicenseStatus
                FssaiService.sync_license_expiration(db, kitchen.license)
                if kitchen.license.status == LicenseStatus.EXPIRED:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Cannot open kitchen: FSSAI Food License has expired. Please renew your license."
                    )
                if kitchen.license.status != LicenseStatus.VERIFIED:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Cannot open kitchen: FSSAI Food License is not verified (Status: {kitchen.license.status.value if hasattr(kitchen.license.status, 'value') else kitchen.license.status})."
                    )

        for field, value in update_dict.items():
            setattr(kitchen, field, value)
        kitchen.updated_at = _utc_now()
        db.commit()
        db.refresh(kitchen)
        return kitchen

    @staticmethod
    def get_notifications(db: Session, user: User, limit: int = 50) -> List[Notification]:
        return db.query(Notification).filter(Notification.user_id == user.id).order_by(Notification.created_at.desc()).limit(limit).all()

    @staticmethod
    def mark_notification_read(db: Session, user: User, notification_id: str) -> None:
        notif = db.query(Notification).filter(Notification.id == notification_id, Notification.user_id == user.id).first()
        if notif:
            notif.is_read = True
            db.commit()

    @staticmethod
    def mark_all_notifications_read(db: Session, user: User) -> int:
        count = db.query(Notification).filter(
            Notification.user_id == user.id,
            Notification.is_read == False
        ).update({"is_read": True})
        db.commit()
        return count
