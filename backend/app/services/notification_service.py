"""
Centralized Platform Notification Service.
Manages dispatching and lifecycle of real database-backed notifications for platform administrators and other roles.
Prevents duplicate notifications for the same real entity/event.
"""
from datetime import datetime, timezone
import json
import logging
from typing import Optional, List, Dict, Any
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc

from backend.app.models.user import User, KitchenProfile
from backend.app.models.platform import Notification
from backend.app.models.order import Order, Payment
from backend.app.models.menu import Ingredient
from backend.app.models.enums import UserRole, OrderStatus, PaymentStatus

logger = logging.getLogger("cloudkitchen.notifications")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_event_category(event_type: str) -> str:
    """Categorizes an event_type into one of the standard filter tabs."""
    t = (event_type or "").upper()
    if "KITCHEN" in t or "REGISTRATION" in t or "ONBOARD" in t:
        return "KITCHEN"
    if "PAYMENT" in t or "REFUND" in t:
        return "PAYMENTS"
    if "ORDER" in t or "DELIVER" in t:
        return "ORDERS"
    if "STOCK" in t or "INVENTORY" in t or "RESTOCK" in t:
        return "INVENTORY"
    return "SYSTEM"


class NotificationService:
    @staticmethod
    def create_admin_notification(
        db: Session,
        title: str,
        message: str,
        event_type: str = "SYSTEM",
        metadata: Optional[Dict[str, Any]] = None,
        dedupe_key: Optional[str] = None
    ) -> List[Notification]:
        """Convenience method to dispatch an admin notification with title/message arguments."""
        return NotificationService.notify_admins(
            db=db,
            event_type=event_type,
            title=title,
            message=message,
            metadata=metadata,
            dedupe_key=dedupe_key
        )

    @staticmethod
    def notify_user(
        db: Session,
        user_id: str,
        title: str,
        message: str,
        event_type: str = "NOTIFICATION_CREATED",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Notification:
        """
        Dispatches a notification to a specific user and emits a real-time event.
        """
        meta_str = json.dumps(metadata) if metadata else None
        notif = Notification(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=title,
            message=message,
            event_type=event_type,
            is_read=False,
            metadata_json=meta_str,
            created_at=utc_now()
        )
        db.add(notif)
        try:
            from backend.app.websockets.connection_manager import ws_manager
            ws_manager.publish_event(
                event_type="NOTIFICATION_NEW",
                data={
                    "id": notif.id,
                    "user_id": user_id,
                    "title": title,
                    "message": message,
                    "event_type": event_type,
                    "created_at": notif.created_at.isoformat() if notif.created_at else None,
                },
                target_user_id=user_id,
            )
        except Exception:
            pass
        return notif

    @staticmethod
    def notify_admins(
        db: Session,
        event_type: str,
        title: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
        dedupe_key: Optional[str] = None
    ) -> List[Notification]:
        """
        Dispatches a notification to all active platform administrators.
        Guarantees deduplication for identical real events/entities.
        """
        admins = db.query(User).filter(
            User.role == UserRole.ADMIN,
            User.is_active == True
        ).all()
        if not admins:
            return []

        created_notifs = []
        meta_str = json.dumps(metadata) if metadata else None
        entity_id = metadata.get("entity_id") if metadata else None

        for admin in admins:
            # Check deduplication
            q = db.query(Notification).filter(
                Notification.user_id == admin.id,
                Notification.event_type == event_type
            )

            # If dedupe_key provided, or entity_id provided in metadata
            is_duplicate = False
            if entity_id:
                # Query recent notifications with this event type
                existing = q.order_by(desc(Notification.created_at)).limit(20).all()
                for ex in existing:
                    if ex.metadata_json:
                        try:
                            m = json.loads(ex.metadata_json)
                            if m.get("entity_id") == entity_id:
                                is_duplicate = True
                                break
                        except Exception:
                            pass
            elif dedupe_key:
                existing = q.order_by(desc(Notification.created_at)).limit(20).all()
                for ex in existing:
                    if ex.metadata_json:
                        try:
                            m = json.loads(ex.metadata_json)
                            if m.get("dedupe_key") == dedupe_key:
                                is_duplicate = True
                                break
                        except Exception:
                            pass

            if is_duplicate:
                continue

            notif = Notification(
                id=str(uuid.uuid4()),
                user_id=admin.id,
                title=title,
                message=message,
                event_type=event_type,
                is_read=False,
                metadata_json=meta_str,
                created_at=utc_now()
            )
            db.add(notif)
            created_notifs.append(notif)

        if created_notifs:
            try:
                db.flush()
            except Exception as e:
                logger.warning(f"Error flushing notifications: {e}")

            try:
                from backend.app.websockets.connection_manager import ws_manager
                for n in created_notifs:
                    ws_manager.publish_event(
                        event_type="NOTIFICATION_NEW",
                        data={
                            "id": n.id,
                            "user_id": n.user_id,
                            "title": n.title,
                            "message": n.message,
                            "event_type": n.event_type,
                            "created_at": n.created_at.isoformat() if n.created_at else None,
                        },
                        target_user_id=n.user_id,
                    )
            except Exception as ws_err:
                logger.warning(f"Error publishing real-time admin notification event: {ws_err}")

        return created_notifs

    @staticmethod
    def sync_admin_notifications_from_platform(db: Session, admin_id: Optional[str] = None) -> int:
        """
        Idempotent sync: Inspects real database records (kitchens, orders, payments, low inventory)
        and ensures active administrators have notifications for real historical platform events.
        Never fabricates mock data; only reads actual existing database rows.
        """
        admins_query = db.query(User).filter(User.role == UserRole.ADMIN, User.is_active == True)
        if admin_id:
            admins_query = admins_query.filter(User.id == admin_id)
        admins = admins_query.all()
        if not admins:
            return 0

        created_count = 0

        for admin in admins:
            # 1. Existing Kitchen Profiles
            kitchens = db.query(KitchenProfile).all()
            for k in kitchens:
                # Check registration request notification
                existing_reg = db.query(Notification).filter(
                    Notification.user_id == admin.id,
                    Notification.event_type == "KITCHEN_REGISTRATION_REQUEST"
                ).all()
                has_reg = any(
                    (json.loads(n.metadata_json).get("entity_id") == k.id if n.metadata_json else False)
                    for n in existing_reg
                )
                if not has_reg:
                    owner_name = k.user.full_name if (k.user and k.user.full_name) else "Kitchen Owner"
                    db.add(Notification(
                        id=str(uuid.uuid4()),
                        user_id=admin.id,
                        title="New Kitchen Registration Request",
                        message=f"Kitchen '{k.kitchen_name}' registered by {owner_name} (Status: {k.approval_status}).",
                        event_type="KITCHEN_REGISTRATION_REQUEST",
                        is_read=True if k.is_approved else False,
                        metadata_json=json.dumps({"entity_type": "kitchen", "entity_id": k.id, "link": "/admin/kitchen-owners"}),
                        created_at=k.created_at or utc_now()
                    ))
                    created_count += 1

                # If approved, ensure approval notification exists
                if k.is_approved:
                    existing_appr = db.query(Notification).filter(
                        Notification.user_id == admin.id,
                        Notification.event_type == "KITCHEN_APPROVED"
                    ).all()
                    has_appr = any(
                        (json.loads(n.metadata_json).get("entity_id") == k.id if n.metadata_json else False)
                        for n in existing_appr
                    )
                    if not has_appr:
                        db.add(Notification(
                            id=str(uuid.uuid4()),
                            user_id=admin.id,
                            title=f"Kitchen Approved: {k.kitchen_name}",
                            message=f"Kitchen '{k.kitchen_name}' was verified and approved.",
                            event_type="KITCHEN_APPROVED",
                            is_read=True,
                            metadata_json=json.dumps({"entity_type": "kitchen", "entity_id": k.id, "link": "/admin/kitchen-owners"}),
                            created_at=k.updated_at or k.created_at or utc_now()
                        ))
                        created_count += 1

            # 2. Existing Real Orders
            orders = db.query(Order).order_by(desc(Order.created_at)).limit(30).all()
            for ord_row in orders:
                existing_ord = db.query(Notification).filter(
                    Notification.user_id == admin.id,
                    Notification.event_type == "ORDER_CREATED"
                ).all()
                has_ord = any(
                    (json.loads(n.metadata_json).get("entity_id") == ord_row.id if n.metadata_json else False)
                    for n in existing_ord
                )
                if not has_ord:
                    k_name = ord_row.kitchen.kitchen_name if ord_row.kitchen else "Kitchen"
                    c_name = ord_row.customer.full_name if ord_row.customer else "Customer"
                    db.add(Notification(
                        id=str(uuid.uuid4()),
                        user_id=admin.id,
                        title=f"New Order #{ord_row.order_number}",
                        message=f"Order #{ord_row.order_number} for ₹{ord_row.total_amount:.2f} placed by {c_name} at {k_name}.",
                        event_type="ORDER_CREATED",
                        is_read=ord_row.status == OrderStatus.DELIVERED,
                        metadata_json=json.dumps({
                            "entity_type": "order",
                            "entity_id": ord_row.id,
                            "order_number": ord_row.order_number,
                            "link": "/admin/orders"
                        }),
                        created_at=ord_row.created_at or utc_now()
                    ))
                    created_count += 1

                # If delivered, ensure delivery notification exists
                if ord_row.status == OrderStatus.DELIVERED:
                    existing_del = db.query(Notification).filter(
                        Notification.user_id == admin.id,
                        Notification.event_type == "ORDER_DELIVERED"
                    ).all()
                    has_del = any(
                        (json.loads(n.metadata_json).get("entity_id") == ord_row.id if n.metadata_json else False)
                        for n in existing_del
                    )
                    if not has_del:
                        db.add(Notification(
                            id=str(uuid.uuid4()),
                            user_id=admin.id,
                            title=f"Order #{ord_row.order_number} Delivered",
                            message=f"Order #{ord_row.order_number} has been delivered successfully.",
                            event_type="ORDER_DELIVERED",
                            is_read=True,
                            metadata_json=json.dumps({
                                "entity_type": "order",
                                "entity_id": ord_row.id,
                                "order_number": ord_row.order_number,
                                "link": "/admin/orders"
                            }),
                            created_at=ord_row.updated_at or ord_row.created_at or utc_now()
                        ))
                        created_count += 1

            # 3. Existing Real Payments
            payments = db.query(Payment).order_by(desc(Payment.created_at)).limit(30).all()
            for pay in payments:
                existing_pay = db.query(Notification).filter(
                    Notification.user_id == admin.id,
                    Notification.event_type == "PAYMENT_RECEIVED"
                ).all()
                has_pay = any(
                    (json.loads(n.metadata_json).get("entity_id") == pay.id if n.metadata_json else False)
                    for n in existing_pay
                )
                if not has_pay:
                    prov = getattr(pay, "payment_provider", "COD") or "COD"
                    db.add(Notification(
                        id=str(uuid.uuid4()),
                        user_id=admin.id,
                        title=f"Payment Received: ₹{pay.amount:.2f}",
                        message=f"Payment of ₹{pay.amount:.2f} received via {prov} (Status: {pay.status.value if hasattr(pay.status, 'value') else pay.status}).",
                        event_type="PAYMENT_RECEIVED",
                        is_read=True,
                        metadata_json=json.dumps({
                            "entity_type": "payment",
                            "entity_id": pay.id,
                            "order_id": pay.order_id,
                            "link": "/admin/payments"
                        }),
                        created_at=pay.created_at or utc_now()
                    ))
                    created_count += 1

            # 4. Low stock ingredients
            low_ingredients = db.query(Ingredient).filter(
                Ingredient.current_stock <= Ingredient.minimum_stock_threshold
            ).all()
            for ing in low_ingredients:
                existing_low = db.query(Notification).filter(
                    Notification.user_id == admin.id,
                    Notification.event_type == "LOW_STOCK"
                ).all()
                has_low = any(
                    (json.loads(n.metadata_json).get("entity_id") == ing.id if n.metadata_json else False)
                    for n in existing_low
                )
                if not has_low:
                    k_name = ing.kitchen.kitchen_name if ing.kitchen else "Kitchen"
                    db.add(Notification(
                        id=str(uuid.uuid4()),
                        user_id=admin.id,
                        title=f"Low Stock: {ing.name}",
                        message=f"{k_name} stock for {ing.name} is at {ing.current_stock:.1f} {ing.unit} (threshold: {ing.minimum_stock_threshold:.1f}).",
                        event_type="LOW_STOCK",
                        is_read=False,
                        metadata_json=json.dumps({
                            "entity_type": "inventory",
                            "entity_id": ing.id,
                            "kitchen_id": ing.kitchen_id,
                            "link": "/admin/inventory"
                        }),
                        created_at=ing.updated_at or ing.created_at or utc_now()
                    ))
                    created_count += 1

        if created_count > 0:
            try:
                db.commit()
            except Exception as e:
                db.rollback()
                logger.warning(f"Failed to commit initial notification sync: {e}")

        return created_count
