from fastapi.responses import FileResponse
from backend.app.models.enums import LicenseStatus
from backend.app.models.license import KitchenLicense, KitchenLicenseDocument
from backend.app.schemas.license import (
    KitchenLicenseResponse,
    KitchenLicenseDocumentResponse,
    LicenseVerificationRequest,
    LicenseCorrectionRequest,
    LicenseRejectionRequest,
)
"""
Admin API Router — Platform Administration Endpoints.
Guarded by require_admin dependency.
Provides oversight for:
  - System dashboard metrics
  - User management (Customers, Kitchen Owners, Admins)
  - Kitchen approval workflow (Pending, Approve, Reject, Suspend)
  - Order & Payment monitoring
  - Platform-wide Menu, Inventory, and Waste oversight
  - Analytics & Audit Logs
  - Promotions management
"""
import logging
from datetime import datetime, timezone, timedelta
import json
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status

logger = logging.getLogger(__name__)
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, or_, case, and_

from backend.app.core.database import get_db
from backend.app.core.deps import require_admin
from backend.app.models.enums import (
    UserRole,
    OrderStatus,
    PaymentStatus,
    InventoryStatus,
)
from backend.app.models.user import User, KitchenProfile, CustomerProfile, UserSession, Address
from backend.app.models.menu import MenuItem, Ingredient, MenuItemIngredient
from backend.app.models.inventory import Inventory, WasteRecord, InventoryTransaction, Purchase
from backend.app.models.order import Order, OrderItem, Payment, Review, Favorite, CancellationRequest
from backend.app.models.license import KitchenLicense, KitchenLicenseDocument
from backend.app.models.platform import Notification, Promotion, DemandPrediction, AuditLog
from backend.app.core.email import email_service
from backend.app.core.database import is_protected_real_user_email
from backend.app.services.kitchen_service import KitchenService

router = APIRouter(prefix="/admin", tags=["Admin Portal"])


# ── Schemas ───────────────────────────────────────────────────────────────────
class RejectionRequest(BaseModel):
    reason: Optional[str] = "Kitchen profile does not meet platform onboarding requirements."


class UserStatusUpdateRequest(BaseModel):
    status: str  # ACTIVE, INACTIVE, SUSPENDED


class BatchRemoveKitchenOwnersRequest(BaseModel):
    kitchen_ids: List[str]


class PromotionCreateRequest(BaseModel):
    code: str
    title: Optional[str] = None
    description: Optional[str] = None
    discount_percent: float = Field(0.0, ge=0, le=100)
    discount_amount: float = Field(0.0, ge=0)
    max_discount_amount: Optional[float] = None
    min_order_amount: float = Field(0.0, ge=0)
    usage_limit: Optional[int] = None
    per_user_limit: Optional[int] = 1
    is_active: bool = True
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None


class PromotionUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    discount_percent: Optional[float] = Field(None, ge=0, le=100)
    discount_amount: Optional[float] = Field(None, ge=0)
    max_discount_amount: Optional[float] = None
    min_order_amount: Optional[float] = Field(None, ge=0)
    usage_limit: Optional[int] = None
    per_user_limit: Optional[int] = None
    is_active: Optional[bool] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None



class AdminProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    phone_number: Optional[str] = None


def _utc_now():
    return datetime.now(timezone.utc)


PROTECTED_OWNER_EMAILS = {
    "b23it030@kitsw.ac.in",
    "sonyvengala7@gmail.com",
}


def _is_protected_kitchen_owner(kitchen: Optional[KitchenProfile], user: Optional[User] = None) -> bool:
    """
    Check if a kitchen or owner user corresponds to the two legitimate protected kitchen owners:
      - Rohith Kalli: b23it030@kitsw.ac.in (KITS Gourmet Cloud Kitchen)
      - VENGALA SONY: sonyvengala7@gmail.com (VENGALA SONY's Kitchen)
    These accounts must NEVER be deleted or archived by administrative actions.
    """
    if user and user.email:
        clean_email = user.email.strip().lower()
        if clean_email in PROTECTED_OWNER_EMAILS:
            return True
    if kitchen:
        if kitchen.user and kitchen.user.email:
            clean_email = kitchen.user.email.strip().lower()
            if clean_email in PROTECTED_OWNER_EMAILS:
                return True
        k_name = (kitchen.kitchen_name or "").strip().lower()
        if k_name in ["kits gourmet cloud kitchen", "vengala sony's kitchen", "vengala sonys kitchen"]:
            return True
    return False



def _format_user(
    u: User,
    current_admin: Optional[User] = None,
    db: Optional[Session] = None,
    active_admin_count: Optional[int] = None,
    precomputed_orders: Optional[int] = None,
    precomputed_kitchen_orders: Optional[int] = None,
    precomputed_reviews: Optional[int] = None,
) -> Dict[str, Any]:
    names = (u.full_name or "").split(" ", 1)
    first = names[0] if names else ""
    last = names[1] if len(names) > 1 else ""

    clean_email = (u.email or "").strip().lower()

    # 1. Self protection check
    is_self = False
    if current_admin:
        is_self = bool(
            u.id == current_admin.id
            or (current_admin.email and clean_email == current_admin.email.strip().lower())
        )

    # 2. Last active administrator check
    is_last_admin = False
    if u.role == UserRole.ADMIN and u.is_active:
        if active_admin_count is None and db is not None:
            active_admin_count = (
                db.query(func.count(User.id))
                .filter(User.role == UserRole.ADMIN, User.is_active == True)
                .scalar()
                or 0
            )
        if active_admin_count is not None and active_admin_count <= 1:
            is_last_admin = True

    # 3. System / Root bootstrap administrator
    is_root_admin = (clean_email == "admin@cloudkitchen.com")
    is_system_account = is_root_admin

    # 4. Protection status & exact reason
    # Protection rules strictly apply to:
    # - The currently authenticated administrator (Self-protection: cannot self-suspend or delete)
    # - The last active administrator (Platform requirement)
    # - The root bootstrap administrator (admin@cloudkitchen.com)
    # Ordinary CUSTOMER and KITCHEN_OWNER accounts are not marked as protected system accounts.
    if is_self:
        is_protected = True
        protection_reason = (
            "Current Authenticated Admin (Self-protection: You cannot suspend or delete your currently authenticated account)"
        )
        can_suspend = False
        can_delete = False
    elif is_last_admin:
        is_protected = True
        protection_reason = (
            "Last Active Administrator (Platform security policy requires at least one active administrator)"
        )
        can_suspend = False
        can_delete = False
    elif is_root_admin:
        is_protected = True
        protection_reason = (
            "Root System Administrator (Primary bootstrap administrator cannot be deleted or suspended)"
        )
        can_suspend = False
        can_delete = False
    else:
        is_protected = False
        protection_reason = None
        can_suspend = True
        can_delete = True

    # 5. Linked business records evaluation
    order_count = precomputed_orders if precomputed_orders is not None else 0
    kitchen_orders = precomputed_kitchen_orders if precomputed_kitchen_orders is not None else 0
    review_count = precomputed_reviews if precomputed_reviews is not None else 0

    if db is not None and precomputed_orders is None:
        order_count = db.query(func.count(Order.id)).filter(Order.customer_id == u.id).scalar() or 0
        if getattr(u, "kitchen_profile", None):
            kitchen_orders = (
                db.query(func.count(Order.id))
                .filter(Order.kitchen_id == u.kitchen_profile.id)
                .scalar()
                or 0
            )
        review_count = db.query(func.count(Review.id)).filter(Review.customer_id == u.id).scalar() or 0

    has_business_records = bool(order_count > 0 or kitchen_orders > 0 or review_count > 0)
    delete_action_type = "archive" if has_business_records else "delete"

    return {
        "id": u.id,
        "email": u.email,
        "first_name": first,
        "last_name": last,
        "full_name": u.full_name or "",
        "role": u.role.value if hasattr(u.role, "value") else str(u.role),
        "status": "ACTIVE" if u.is_active else "INACTIVE",
        "is_email_verified": u.is_verified,
        "created_at": u.created_at.isoformat() if u.created_at else _utc_now().isoformat(),
        "last_login_at": None,
        "is_protected": is_protected,
        "protection_reason": protection_reason,
        "can_suspend": can_suspend,
        "can_delete": can_delete,
        "is_self": is_self,
        "is_last_admin": is_last_admin,
        "is_system_account": is_system_account,
        "has_business_records": has_business_records,
        "orders_count": order_count,
        "kitchen_orders": kitchen_orders,
        "reviews_count": review_count,
        "delete_action_type": delete_action_type,
    }


def _format_kitchen(k: KitchenProfile) -> Dict[str, Any]:
    owner_info = None
    names = []
    if k.user:
        names = (k.user.full_name or "").split(" ", 1)
        owner_info = {
            "id": k.user.id,
            "email": k.user.email,
            "first_name": names[0] if names else "",
            "last_name": names[1] if len(names) > 1 else "",
            "status": "ACTIVE" if k.user.is_active else "INACTIVE",
            "is_email_verified": k.user.is_verified,
            "phone_number": getattr(k.user, "phone_number", None) or k.phone or "",
        }
    
    raw_status = getattr(k, "approval_status", None) or ("APPROVED" if k.is_approved else "PENDING")
    if raw_status in ["PENDING_APPROVAL", "PENDING"]:
        normalized_status = "PENDING"
    elif raw_status == "APPROVED":
        normalized_status = "APPROVED"
    elif raw_status == "REJECTED":
        normalized_status = "REJECTED"
    else:
        normalized_status = raw_status

    first_n = names[0] if names else ""
    last_n = names[1] if len(names) > 1 else ""
    full_n = (k.user.full_name or "").strip() if k.user else ""

    lic = getattr(k, "license", None)
    lic_info = None
    if lic:
        active_docs = [d for d in lic.documents if d.is_active] if getattr(lic, "documents", None) else []
        active_doc = active_docs[0] if active_docs else (lic.documents[0] if getattr(lic, "documents", None) else None)
        lic_status_str = lic.status.value if hasattr(lic.status, "value") else str(lic.status)
        
        parsed_ocr = None
        if getattr(lic, "ocr_extracted_data", None):
            try:
                parsed_ocr = json.loads(lic.ocr_extracted_data) if isinstance(lic.ocr_extracted_data, str) else lic.ocr_extracted_data
            except Exception:
                parsed_ocr = {"raw": lic.ocr_extracted_data}
        elif active_doc and getattr(active_doc, "ocr_extracted_data", None):
            try:
                parsed_ocr = json.loads(active_doc.ocr_extracted_data) if isinstance(active_doc.ocr_extracted_data, str) else active_doc.ocr_extracted_data
            except Exception:
                parsed_ocr = {"raw": active_doc.ocr_extracted_data}

        lic_info = {
            "id": lic.id,
            "license_number": lic.license_number,
            "raw_license_number": lic.raw_license_number,
            "business_name": lic.business_name,
            "status": lic_status_str,
            "expiry_date": lic.expiry_date.isoformat() if lic.expiry_date else None,
            "issue_date": lic.issue_date.isoformat() if lic.issue_date else None,
            "submission_date": lic.created_at.isoformat() if lic.created_at else None,
            "created_at": lic.created_at.isoformat() if lic.created_at else None,
            "duplicate_flag": lic.duplicate_flag,
            "is_duplicate_flagged": lic.duplicate_flag,
            "duplicate_details": lic.duplicate_details,
            "verification_source": lic.verification_source,
            "verified_at": lic.verified_at.isoformat() if lic.verified_at else None,
            "correction_reason": lic.correction_reason,
            "rejection_reason": lic.rejection_reason,
            "ocr_extracted_data": parsed_ocr,
            "ocr_extracted_number": parsed_ocr.get("extracted_license_number") if isinstance(parsed_ocr, dict) else None,
            "ocr_extracted_name": parsed_ocr.get("extracted_business_name") if isinstance(parsed_ocr, dict) else None,
            "ocr_extracted_expiry": parsed_ocr.get("extracted_expiry_date") if isinstance(parsed_ocr, dict) else None,
            "documents_count": len(lic.documents) if getattr(lic, "documents", None) else 0,
            "active_document": {
                "id": active_doc.id,
                "original_filename": active_doc.original_filename,
                "file_size": active_doc.file_size,
                "mime_type": active_doc.mime_type,
                "document_type": active_doc.document_type,
                "created_at": active_doc.created_at.isoformat(),
            } if active_doc else None,
            "documents": [
                {
                    "id": d.id,
                    "original_filename": d.original_filename,
                    "file_size": d.file_size,
                    "mime_type": d.mime_type,
                    "document_type": d.document_type,
                    "is_active": d.is_active,
                    "created_at": d.created_at.isoformat(),
                } for d in lic.documents
            ] if getattr(lic, "documents", None) else [],
        }

    return {
        "id": k.id,
        "kitchen_name": k.kitchen_name,
        "description": k.description,
        "address": k.address,
        "city": k.city,
        "phone": k.phone or (getattr(k.user, "phone_number", None) if k.user else "") or "",
        "is_open": k.is_open,
        "is_verified": k.user.is_verified if k.user else False,
        "is_email_verified": k.user.is_verified if k.user else False,
        "is_approved": k.is_approved,
        "approval_status": normalized_status,
        "rejection_reason": getattr(k, "rejection_reason", None),
        "rating": k.rating,
        "total_reviews": k.rating_count,
        "created_at": k.created_at.isoformat() if k.created_at else _utc_now().isoformat(),
        "owner": owner_info,
        # Flattened conveniences for kitchen-owners tables
        "owner_name": full_n,
        "first_name": first_n,
        "last_name": last_n,
        "email": k.user.email if k.user else "",
        "status": "ACTIVE" if (k.user and k.user.is_active) else "INACTIVE",
        "is_protected": bool(k.user and (k.user.email or "").strip().lower() == "admin@cloudkitchen.com"),
        "protection_reason": (
            "Root System Administrator (Primary platform bootstrap administrator)"
            if (k.user and (k.user.email or "").strip().lower() == "admin@cloudkitchen.com")
            else None
        ),
        "license": lic_info,
        "license_number": lic.license_number if lic else None,
        "license_status": lic_info["status"] if lic_info else "UNREGISTERED",
        "license_duplicate": lic.duplicate_flag if lic else False,
        "license_expiry": lic_info["expiry_date"] if lic_info else None,
    }


# ── 1. Dashboard ──────────────────────────────────────────────────────────────
@router.get("/dashboard")
def get_dashboard_stats(
    scenario: str = Query("production", description="Filter: 'production' (default, excludes test orders), 'test_scenario' (only test orders), or 'all'"),
    start_date: Optional[str] = Query(None, description="ISO start date filter (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="ISO end date filter (YYYY-MM-DD)"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    # Single-pass aggregated user counts (excluding ADMIN accounts from total_users)
    user_counts = db.query(
        func.sum(case((User.role.in_([UserRole.CUSTOMER, UserRole.KITCHEN_OWNER]), 1), else_=0)).label("total_users"),
        func.sum(case((User.role == UserRole.CUSTOMER, 1), else_=0)).label("customers"),
        func.sum(case((User.role == UserRole.KITCHEN_OWNER, 1), else_=0)).label("kitchen_owners")
    ).first()

    total_users = int(user_counts.total_users or 0) if user_counts else 0
    customers = int(user_counts.customers or 0) if user_counts else 0
    kitchen_owners = int(user_counts.kitchen_owners or 0) if user_counts else 0
    kitchens = db.query(func.count(KitchenProfile.id)).scalar() or 0

    # Scenario filtering: strictly isolate synthetic validation fixtures from live metrics
    if scenario == "test_scenario":
        scenario_filter = or_(Order.is_test == True, Order.order_number.like("TEST-%"))
    elif scenario == "all":
        scenario_filter = True
    else:  # "production" (default)
        scenario_filter = and_(
            or_(Order.is_test == False, Order.is_test.is_(None)),
            ~Order.order_number.like("TEST-%")
        )

    # Date filters
    date_filters = []
    if start_date:
        try:
            sd = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            if sd.tzinfo is None:
                sd = sd.replace(tzinfo=timezone.utc)
            date_filters.append(Order.created_at >= sd)
        except Exception:
            pass
    if end_date:
        try:
            ed = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            if ed.tzinfo is None:
                ed = ed.replace(tzinfo=timezone.utc)
            date_filters.append(Order.created_at <= ed)
        except Exception:
            pass

    pending_statuses = [
        OrderStatus.ORDER_PLACED,
        OrderStatus.PAYMENT_CONFIRMED
    ]
    cancelled_statuses = [
        OrderStatus.CANCELLED,
        OrderStatus.REJECTED,
        OrderStatus.REFUNDED
    ]
    in_flight_statuses = [
        OrderStatus.KITCHEN_ACCEPTED,
        OrderStatus.PREPARING,
        OrderStatus.READY,
        OrderStatus.OUT_FOR_DELIVERY
    ]

    base_order_query = db.query(
        func.count(Order.id).label("total_orders"),
        func.sum(case((Order.status.in_(pending_statuses), 1), else_=0)).label("pending_orders"),
        func.sum(case((Order.status == OrderStatus.DELIVERED, 1), else_=0)).label("completed_orders"),
        func.sum(case((Order.status.in_(cancelled_statuses), 1), else_=0)).label("cancelled_orders"),
        func.sum(Order.total_amount).label("gross_order_value"),
        # Realized delivered revenue: strictly delivered, successfully paid, non-cancelled, non-refunded
        func.sum(case((
            and_(
                Order.status == OrderStatus.DELIVERED,
                Order.payment_status == PaymentStatus.SUCCESS,
                ~Order.status.in_(cancelled_statuses),
                Order.payment_status != PaymentStatus.REFUNDED
            ),
            Order.total_amount
        ), else_=0.0)).label("revenue"),
        # Collected payments: non-cancelled orders with confirmed payment
        func.sum(case((
            and_(
                Order.payment_status == PaymentStatus.SUCCESS,
                ~Order.status.in_(cancelled_statuses),
                Order.payment_status != PaymentStatus.REFUNDED
            ),
            Order.total_amount
        ), else_=0.0)).label("collected_payments"),
        # Total refunds
        func.sum(case((
            or_(
                Order.payment_status == PaymentStatus.REFUNDED,
                Order.status.in_(cancelled_statuses)
            ),
            Order.total_amount
        ), else_=0.0)).label("refunded_amount"),
        # In-flight paid orders
        func.sum(case((
            and_(
                Order.status.in_(in_flight_statuses),
                Order.payment_status == PaymentStatus.SUCCESS,
                ~Order.status.in_(cancelled_statuses)
            ),
            Order.total_amount
        ), else_=0.0)).label("in_flight_revenue")
    ).filter(scenario_filter)

    if date_filters:
        base_order_query = base_order_query.filter(*date_filters)

    order_metrics = base_order_query.first()

    total_orders = int(order_metrics.total_orders or 0) if order_metrics else 0
    pending_orders = int(order_metrics.pending_orders or 0) if order_metrics else 0
    completed_orders = int(order_metrics.completed_orders or 0) if order_metrics else 0
    cancelled_orders = int(order_metrics.cancelled_orders or 0) if order_metrics else 0
    gross_order_value = round(float(order_metrics.gross_order_value or 0.0), 2) if order_metrics else 0.0
    revenue = round(float(order_metrics.revenue or 0.0), 2) if order_metrics else 0.0
    collected_payments = round(float(order_metrics.collected_payments or 0.0), 2) if order_metrics else 0.0
    refunded_amount = round(float(order_metrics.refunded_amount or 0.0), 2) if order_metrics else 0.0
    in_flight_revenue = round(float(order_metrics.in_flight_revenue or 0.0), 2) if order_metrics else 0.0
    platform_commission = round(revenue * 0.15, 2)

    low_stock = db.query(func.count(Inventory.id)).filter(
        Inventory.status == InventoryStatus.LOW_STOCK
    ).scalar() or 0

    reviews = db.query(func.count(Review.id)).scalar() or 0
    waste_records = db.query(func.count(WasteRecord.id)).scalar() or 0

    return {
        "total_users": total_users,
        "customers": customers,
        "kitchen_owners": kitchen_owners,
        "kitchens": kitchens,
        "total_orders": total_orders,
        "pending_orders": pending_orders,
        "completed_orders": completed_orders,
        "cancelled_orders": cancelled_orders,
        "revenue": float(revenue),
        "gross_order_value": float(gross_order_value),
        "collected_payments": float(collected_payments),
        "refunded_amount": float(refunded_amount),
        "in_flight_revenue": float(in_flight_revenue),
        "platform_commission": float(platform_commission),
        "low_stock_items": low_stock,
        "reviews": reviews,
        "waste_records": waste_records,
        "scenario": scenario,
        "date_range": f"{start_date} to {end_date}" if (start_date or end_date) else "all_time",
    }


# ── 2. User Management ────────────────────────────────────────────────────────
@router.get("/users")
def get_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    verified: Optional[bool] = Query(None),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    q = db.query(User)
    if search and isinstance(search, str):
        term = f"%{search.lower()}%"
        q = q.filter(func.lower(User.email).like(term) | func.lower(User.full_name).like(term))
    if role and isinstance(role, str):
        q = q.filter(User.role == role)
    if status and isinstance(status, str):
        if status == "ACTIVE":
            q = q.filter(User.is_active == True)
        elif status in ["INACTIVE", "SUSPENDED"]:
            q = q.filter(User.is_active == False)
    if verified is not None and isinstance(verified, bool):
        q = q.filter(User.is_verified == verified)

    total = q.count()
    users = q.order_by(User.created_at.desc()).offset(skip).limit(limit).all()

    # Precompute active admin count and counts in batch for optimal efficiency
    active_admin_count = (
        db.query(func.count(User.id))
        .filter(User.role == UserRole.ADMIN, User.is_active == True)
        .scalar()
        or 0
    )

    user_ids = [u.id for u in users]
    customer_order_counts = {}
    customer_review_counts = {}
    kitchen_order_counts = {}

    if user_ids:
        for cid, cnt in (
            db.query(Order.customer_id, func.count(Order.id))
            .filter(Order.customer_id.in_(user_ids))
            .group_by(Order.customer_id)
            .all()
        ):
            customer_order_counts[cid] = cnt

        for cid, cnt in (
            db.query(Review.customer_id, func.count(Review.id))
            .filter(Review.customer_id.in_(user_ids))
            .group_by(Review.customer_id)
            .all()
        ):
            customer_review_counts[cid] = cnt

        kitchens = db.query(KitchenProfile).filter(KitchenProfile.user_id.in_(user_ids)).all()
        kitchen_ids = [k.id for k in kitchens]
        k_user_map = {k.id: k.user_id for k in kitchens}
        if kitchen_ids:
            for kid, cnt in (
                db.query(Order.kitchen_id, func.count(Order.id))
                .filter(Order.kitchen_id.in_(kitchen_ids))
                .group_by(Order.kitchen_id)
                .all()
            ):
                uid = k_user_map.get(kid)
                if uid:
                    kitchen_order_counts[uid] = cnt

    return {
        "users": [
            _format_user(
                u,
                current_admin=admin,
                db=db,
                active_admin_count=active_admin_count,
                precomputed_orders=customer_order_counts.get(u.id, 0),
                precomputed_kitchen_orders=kitchen_order_counts.get(u.id, 0),
                precomputed_reviews=customer_review_counts.get(u.id, 0),
            )
            for u in users
        ],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/users/{user_id}")
def get_user_detail(
    user_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    data = _format_user(user, current_admin=admin, db=db)
    if user.kitchen_profile:
        data["kitchen_profile"] = _format_kitchen(user.kitchen_profile)
    return data


@router.patch("/users/{user_id}/status")
def update_user_status(
    user_id: str,
    req: UserStatusUpdateRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    clean_email = (user.email or "").strip().lower()

    # 1. Prevent an administrator from deactivating their own account
    if (user.id == admin.id or clean_email == (admin.email or "").strip().lower()) and req.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Self-deactivation is prohibited. Administrators cannot suspend or deactivate their own currently authenticated account."
        )

    # 2. Protect the last active administrator
    if user.role == UserRole.ADMIN and user.is_active and req.status != "ACTIVE":
        other_active_admins = db.query(func.count(User.id)).filter(
            User.role == UserRole.ADMIN,
            User.is_active == True,
            User.id != user.id
        ).scalar() or 0
        if other_active_admins == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate the last active administrator. At least one active administrator must remain."
            )

    # 3. Protect root system accounts from deactivation
    if req.status != "ACTIVE":
        if clean_email == "admin@cloudkitchen.com":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot suspend root system administrator account '{user.full_name}' ({user.email})."
            )

    db._allow_auth_service_update = True
    user.is_active = (req.status == "ACTIVE")
    if not user.is_active:
        db.query(UserSession).filter(UserSession.user_id == user.id).update({"is_revoked": True})
        if user.kitchen_profile:
            user.kitchen_profile.is_open = False

    db.add(AuditLog(
        user_id=admin.id,
        action="USER_STATUS_UPDATED",
        entity_name="User",
        entity_id=user.id,
        details_json=json.dumps({"new_status": req.status, "email": user.email, "updated_by": admin.email})
    ))

    db.commit()
    db.refresh(user)
    return _format_user(user, current_admin=admin, db=db)


@router.delete("/users/{user_id}")
def delete_user(
    user_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Safely delete or archive a user account:
    - Never allows an administrator to delete their own account.
    - Protects the last active administrator.
    - Soft-deletes/archives users who have historical orders, reviews, or kitchen records.
    - Permanently deletes accounts only when no dependent business records exist.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    clean_email = (user.email or "").strip().lower()

    # 0. Protect confirmed root bootstrap administrator
    if clean_email == "admin@cloudkitchen.com":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete root system administrator account '{user.full_name}' ({user.email})."
        )

    # 1. Never allow the logged-in administrator to delete their own account
    if user.id == admin.id or clean_email == (admin.email or "").strip().lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Self-deletion is prohibited. Administrators cannot delete their own account."
        )

    # 2. Protect the last active administrator
    if user.role == UserRole.ADMIN and user.is_active:
        other_active_admins = db.query(func.count(User.id)).filter(
            User.role == UserRole.ADMIN,
            User.is_active == True,
            User.id != user.id
        ).scalar() or 0
        if other_active_admins == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete the last active administrator. At least one active administrator must remain."
            )

    # 3. Check for dependent business records
    order_count = db.query(func.count(Order.id)).filter(Order.customer_id == user.id).scalar() or 0
    review_count = db.query(func.count(Review.id)).filter(Review.customer_id == user.id).scalar() or 0
    
    kitchen = db.query(KitchenProfile).filter(KitchenProfile.user_id == user.id).first()
    kitchen_orders = 0
    kitchen_inventory = 0
    has_real_history = False
    if kitchen:
        has_real_history = _has_real_business_history(kitchen, db)
        kitchen_orders = db.query(func.count(Order.id)).filter(Order.kitchen_id == kitchen.id).scalar() or 0
        kitchen_inventory = db.query(func.count(Inventory.id)).filter(Inventory.kitchen_id == kitchen.id).scalar() or 0

    has_business_records = bool(
        order_count > 0
        or review_count > 0
        or kitchen_orders > 0
        or kitchen_inventory > 0
        or has_real_history
    )

    db._allow_auth_service_update = True

    if has_business_records:
        # Soft-deletion / archival: retain all financial and operational history
        user.is_active = False
        db.query(UserSession).filter(UserSession.user_id == user.id).update({"is_revoked": True})
        if kitchen:
            kitchen.is_open = False
            kitchen.is_approved = False
            kitchen.approval_status = "ARCHIVED"
            kitchen.updated_at = _utc_now()

        db.add(AuditLog(
            user_id=admin.id,
            action="USER_ARCHIVED",
            entity_name="User",
            entity_id=user.id,
            details_json=json.dumps({
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role.value if hasattr(user.role, "value") else str(user.role),
                "orders_count": order_count,
                "kitchen_orders": kitchen_orders,
                "reason": "Preserved historical orders, payments, and business records",
                "archived_by": admin.email
            })
        ))
        db.commit()
        return {
            "success": True,
            "action": "archived",
            "message": f"User '{user.full_name}' ({user.email}) has historical orders or business records. Account has been safely deactivated and archived without deleting business history."
        }
    else:
        # Safe permanent deletion: clean up any attached test kitchen and dependent records
        email = user.email
        name = user.full_name
        user_id_str = user.id

        if kitchen:
            _execute_kitchen_removal(kitchen, admin, db)

        db.add(AuditLog(
            user_id=admin.id,
            action="USER_DELETED",
            entity_name="User",
            entity_id=user_id_str,
            details_json=json.dumps({
                "email": email,
                "full_name": name,
                "deleted_by": admin.email
            })
        ))
        db.query(Notification).filter(Notification.user_id == user.id).delete()
        db.query(UserSession).filter(UserSession.user_id == user.id).delete()
        db.query(Address).filter(Address.user_id == user.id).delete()
        db.query(CustomerProfile).filter(CustomerProfile.user_id == user.id).delete()
        db.query(AuditLog).filter(AuditLog.user_id == user.id).update({"user_id": None})
        if db.query(User).filter(User.id == user.id).first():
            db.delete(user)
        db.commit()
        return {
            "success": True,
            "action": "deleted",
            "message": f"User '{name}' ({email}) had no dependent business records and has been permanently removed."
        }



# ── 3. Kitchens & Kitchen Owner Approvals ──────────────────────────────────────
@router.get("/kitchens")
def get_kitchens(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    q = db.query(KitchenProfile)
    if search:
        term = f"%{search.lower()}%"
        q = q.filter(func.lower(KitchenProfile.kitchen_name).like(term) | func.lower(KitchenProfile.city).like(term))
    total = q.count()
    kitchens = q.order_by(KitchenProfile.created_at.desc()).offset(skip).limit(limit).all()
    return {
        "kitchens": [_format_kitchen(k) for k in kitchens],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/kitchen-owners")
def get_kitchen_owners(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    q = db.query(KitchenProfile).outerjoin(User, KitchenProfile.user_id == User.id)
    if search:
        term = f"%{search.lower()}%"
        q = q.filter(
            func.lower(KitchenProfile.kitchen_name).like(term) |
            func.lower(func.coalesce(User.email, "")).like(term) |
            func.lower(func.coalesce(User.full_name, "")).like(term)
        )
    if status:
        if status.upper() in ["PENDING", "PENDING_APPROVAL"]:
            q = q.filter((KitchenProfile.is_approved == False) | (KitchenProfile.approval_status.in_(["PENDING", "PENDING_APPROVAL"])))
        elif status.upper() == "APPROVED":
            q = q.filter(KitchenProfile.is_approved == True, KitchenProfile.approval_status == "APPROVED")
        elif status.upper() == "REJECTED":
            q = q.filter(KitchenProfile.approval_status == "REJECTED")
        elif status.upper() == "ARCHIVED":
            q = q.filter(KitchenProfile.approval_status == "ARCHIVED")

    total = q.count()
    kitchens = q.order_by(KitchenProfile.created_at.desc()).offset(skip).limit(limit).all()
    return {
        "kitchens": [_format_kitchen(k) for k in kitchens],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/kitchen-owners/pending")
def get_pending_kitchen_owners(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    return get_kitchen_owners(skip=skip, limit=limit, search=search, status="PENDING", admin=admin, db=db)


@router.post("/kitchen-owners/{kitchen_id}/approve")
def approve_kitchen_owner(
    kitchen_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    return approve_kitchen(kitchen_id=kitchen_id, admin=admin, db=db)


@router.post("/kitchen-owners/{kitchen_id}/reject")
def reject_kitchen_owner(
    kitchen_id: str,
    req: RejectionRequest = RejectionRequest(),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    return reject_kitchen(kitchen_id=kitchen_id, req=req, admin=admin, db=db)


def _is_test_account_email(email: str) -> bool:
    if not email:
        return False
    e = email.strip().lower()
    from backend.app.core.database import is_protected_real_user_email
    if is_protected_real_user_email(e):
        return False
    return (
        e.endswith("@cloudkitchen.com")
        or e.endswith("@example.com")
        or e.endswith("@test.com")
        or e.endswith("@cloudkitchen.example.com")
        or e.startswith("ko_")
        or e.startswith("cust_")
        or e.startswith("test_")
        or e.startswith("mock_")
        or "test" in e.split("@")[0]
    )


def _has_real_business_history(kitchen: KitchenProfile, db: Session) -> bool:
    """
    Check if a kitchen contains legitimate real-world business data that MUST be preserved.
    Returns True if:
      - Owner is a protected real user
      - Kitchen has any completed financial payments (PaymentStatus.SUCCESS)
      - Kitchen has any fulfilled/delivered orders (status DELIVERED or COMPLETED)
      - Kitchen has customer reviews
      - Kitchen has a verified FSSAI food safety license
      - Kitchen has orders placed by legitimate (non-test) customers
      - Kitchen owner is a non-test user and has orders
    """
    from backend.app.core.database import is_protected_real_user_email
    owner = kitchen.user
    if owner and is_protected_real_user_email(owner.email):
        return True

    # 1. Any completed financial payments (SUCCESS) must always be preserved
    completed_payments_count = (
        db.query(func.count(Payment.id))
        .join(Order, Payment.order_id == Order.id)
        .filter(Order.kitchen_id == kitchen.id, Payment.status == PaymentStatus.SUCCESS)
        .scalar()
        or 0
    )
    if completed_payments_count > 0:
        return True

    # 2. Any fulfilled or delivered orders must be preserved
    delivered_orders_count = (
        db.query(func.count(Order.id))
        .filter(
            Order.kitchen_id == kitchen.id,
            Order.status.in_([OrderStatus.DELIVERED, "COMPLETED"])
        )
        .scalar()
        or 0
    )
    if delivered_orders_count > 0:
        return True

    # 3. Any verified food safety licenses must be preserved
    if kitchen.license and getattr(kitchen.license, "status", None) == "VERIFIED":
        return True

    # 4. Any customer reviews must be preserved
    reviews_count = db.query(func.count(Review.id)).filter(Review.kitchen_id == kitchen.id).scalar() or 0
    if reviews_count > 0:
        return True

    # 5. Any orders placed by real, non-test customers must be preserved
    orders = db.query(Order).filter(Order.kitchen_id == kitchen.id).all()
    for o in orders:
        cust = db.query(User).filter(User.id == o.customer_id).first()
        if cust and not _is_test_account_email(cust.email):
            return True

    # 6. If owner is not a test account and has orders, preserve
    if owner and not _is_test_account_email(owner.email) and len(orders) > 0:
        return True

    # 7. If owner itself placed fulfilled customer orders elsewhere
    if owner:
        user_orders_count = (
            db.query(func.count(Order.id))
            .filter(
                Order.customer_id == owner.id,
                Order.status.in_([OrderStatus.DELIVERED, "COMPLETED"])
            )
            .scalar()
            or 0
        )
        if user_orders_count > 0:
            return True

    return False


def _execute_orphaned_owner_cleanup(orphaned_user: User, admin: User, db: Session) -> dict:
    """
    Safely clean up an orphaned kitchen owner user account that has no kitchen profile.
    """
    user_name = orphaned_user.full_name or "Unknown Owner"
    user_email = orphaned_user.email or "N/A"

    audit_entry = AuditLog(
        user_id=admin.id,
        action="ORPHANED_KITCHEN_OWNER_DELETED",
        entity_name="User",
        entity_id=orphaned_user.id,
        details_json=json.dumps({
            "user_id": orphaned_user.id,
            "full_name": user_name,
            "email": user_email,
            "deleted_by": admin.email,
        })
    )
    db.add(audit_entry)

    db.query(Notification).filter(Notification.user_id == orphaned_user.id).delete()
    db.query(UserSession).filter(UserSession.user_id == orphaned_user.id).delete()
    db.query(Address).filter(Address.user_id == orphaned_user.id).delete()
    db.query(CustomerProfile).filter(CustomerProfile.user_id == orphaned_user.id).delete()
    db.query(AuditLog).filter(AuditLog.user_id == orphaned_user.id).update({"user_id": None})
    db.delete(orphaned_user)
    db.flush()

    return {
        "success": True,
        "action": "removed",
        "message": f"Orphaned kitchen owner account '{user_name}' ({user_email}) has been permanently removed."
    }


def _execute_kitchen_removal(kitchen: KitchenProfile, admin: User, db: Session) -> dict:
    """
    Core business logic for kitchen removal/archival.
    Preserves business history if real orders/payments exist; cleanly removes eligible test records.
    Hard-rejects removal of protected legitimate kitchen owners.
    """
    if kitchen.user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot delete their own kitchen registration."
        )

    owner_user = kitchen.user
    if _is_protected_kitchen_owner(kitchen, owner_user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot remove or archive protected legitimate kitchen owner account '{kitchen.kitchen_name}'."
        )

    has_business_records = _has_real_business_history(kitchen, db)
    db._allow_auth_service_update = True

    kitchen_id_str = kitchen.id
    kitchen_name = kitchen.kitchen_name
    owner_email = owner_user.email if owner_user else "N/A"
    owner_name = owner_user.full_name if owner_user else "N/A"

    if has_business_records:
        if kitchen.approval_status == "ARCHIVED":
            return {
                "success": True,
                "action": "archived",
                "message": f"Kitchen '{kitchen_name}' is already archived. Its financial and order audit records are permanently preserved."
            }

        # Soft-deletion / Archival to preserve financial, customer, and operational history
        kitchen.is_open = False
        kitchen.is_approved = False
        kitchen.approval_status = "ARCHIVED"
        kitchen.updated_at = _utc_now()

        if owner_user:
            owner_user.is_active = False
            db.query(UserSession).filter(UserSession.user_id == owner_user.id).update({"is_revoked": True})

        orders_count = db.query(func.count(Order.id)).filter(Order.kitchen_id == kitchen.id).scalar() or 0
        payments_count = (
            db.query(func.count(Payment.id))
            .join(Order, Payment.order_id == Order.id)
            .filter(Order.kitchen_id == kitchen.id)
            .scalar()
            or 0
        )

        audit_entry = AuditLog(
            user_id=admin.id,
            action="KITCHEN_ARCHIVED",
            entity_name="KitchenProfile",
            entity_id=kitchen_id_str,
            details_json=json.dumps({
                "kitchen_name": kitchen_name,
                "owner_email": owner_email,
                "owner_name": owner_name,
                "orders_count": orders_count,
                "payments_count": payments_count,
                "reason": "Preserved historical orders, payments, and business records",
                "archived_by": admin.email
            })
        )
        db.add(audit_entry)

        from backend.app.services.notification_service import NotificationService
        NotificationService.notify_admins(
            db=db,
            event_type="KITCHEN_ARCHIVED",
            title=f"Kitchen Archived: {kitchen_name}",
            message=f"Kitchen '{kitchen_name}' was safely archived by {admin.email} to preserve {orders_count} historical orders.",
            metadata={"entity_type": "kitchen", "entity_id": kitchen_id_str, "link": "/admin/kitchen-owners"}
        )

        try:
            from backend.app.websockets.connection_manager import ws_manager
            ws_manager.publish_event(
                event_type="KITCHEN_APPROVAL_UPDATED",
                data={
                    "kitchen_id": kitchen_id_str,
                    "action": "archived",
                    "approval_status": "ARCHIVED",
                    "is_approved": False,
                    "is_open": False,
                },
                target_role="ADMIN",
            )
            if owner_user:
                ws_manager.publish_event(
                    event_type="KITCHEN_APPROVAL_UPDATED",
                    data={
                        "kitchen_id": kitchen_id_str,
                        "action": "archived",
                        "approval_status": "ARCHIVED",
                    },
                    target_user_id=owner_user.id,
                )
        except Exception as ws_err:
            logger.warning(f"Error publishing real-time kitchen archival event: {ws_err}")

        return {
            "success": True,
            "action": "archived",
            "message": f"Kitchen '{kitchen_name}' has historical orders or business records. Account has been safely deactivated and archived without deleting business history."
        }
    else:
        # Safe permanent deletion: unfulfilled test/pending/rejected registration with NO real business records
        audit_entry = AuditLog(
            user_id=admin.id,
            action="KITCHEN_DELETED",
            entity_name="KitchenProfile",
            entity_id=kitchen_id_str,
            details_json=json.dumps({
                "kitchen_name": kitchen_name,
                "owner_email": owner_email,
                "owner_name": owner_name,
                "deleted_by": admin.email
            })
        )
        db.add(audit_entry)

        # 1. Clean up reviews, favorites, cancellations, and waste records referencing this kitchen or its orders
        db.query(Review).filter(Review.kitchen_id == kitchen.id).delete()
        db.query(Favorite).filter(Favorite.kitchen_id == kitchen.id).delete()
        db.query(CancellationRequest).filter(CancellationRequest.kitchen_id == kitchen.id).delete()
        db.query(WasteRecord).filter(WasteRecord.kitchen_id == kitchen.id).delete()

        # 2. Clean up synthetic/test orders and dependent order records
        test_orders = db.query(Order).filter(Order.kitchen_id == kitchen.id).all()
        for t_order in test_orders:
            db.query(OrderItem).filter(OrderItem.order_id == t_order.id).delete()
            db.query(Payment).filter(Payment.order_id == t_order.id).delete()
            db.query(Review).filter(Review.order_id == t_order.id).delete()
            db.query(CancellationRequest).filter(CancellationRequest.order_id == t_order.id).delete()
            db.query(WasteRecord).filter(WasteRecord.order_id == t_order.id).delete()
            db.delete(t_order)
        db.flush()

        # 3. Clean up food license & document history
        lic = db.query(KitchenLicense).filter(KitchenLicense.kitchen_id == kitchen.id).first()
        if lic:
            db.query(KitchenLicenseDocument).filter(KitchenLicenseDocument.license_id == lic.id).delete()
            db.delete(lic)

        # 4. Clean up menu items and recipes
        m_items = db.query(MenuItem).filter(MenuItem.kitchen_id == kitchen.id).all()
        for m in m_items:
            db.query(MenuItemIngredient).filter(MenuItemIngredient.menu_item_id == m.id).delete()
            db.query(WasteRecord).filter(WasteRecord.menu_item_id == m.id).delete()
            db.delete(m)

        # 5. Clean up inventory, ledger transactions, purchases, ingredients
        db.query(Inventory).filter(Inventory.kitchen_id == kitchen.id).delete()
        db.query(InventoryTransaction).filter(InventoryTransaction.kitchen_id == kitchen.id).delete()
        db.query(Purchase).filter(Purchase.kitchen_id == kitchen.id).delete()
        db.query(Ingredient).filter(Ingredient.kitchen_id == kitchen.id).delete()

        # 6. Clean up owner notifications and sessions
        if owner_user:
            db.query(Notification).filter(Notification.user_id == owner_user.id).delete()
            db.query(UserSession).filter(UserSession.user_id == owner_user.id).delete()

        db.delete(kitchen)
        db.flush()

        # 7. Clean up owner user if role is KITCHEN_OWNER and has no customer orders and is not protected
        if owner_user and owner_user.role == UserRole.KITCHEN_OWNER and not is_protected_real_user_email(owner_user.email):
            cust_orders = db.query(func.count(Order.id)).filter(Order.customer_id == owner_user.id).scalar() or 0
            if cust_orders == 0:
                db.query(Address).filter(Address.user_id == owner_user.id).delete()
                db.query(CustomerProfile).filter(CustomerProfile.user_id == owner_user.id).delete()
                db.query(AuditLog).filter(AuditLog.user_id == owner_user.id).update({"user_id": None})
                db.delete(owner_user)

        try:
            from backend.app.websockets.connection_manager import ws_manager
            ws_manager.publish_event(
                event_type="KITCHEN_APPROVAL_UPDATED",
                data={
                    "kitchen_id": kitchen_id_str,
                    "action": "deleted",
                    "approval_status": "DELETED",
                },
                target_role="ADMIN",
            )
        except Exception as ws_err:
            logger.warning(f"Error publishing real-time kitchen deletion event: {ws_err}")

        return {
            "success": True,
            "action": "removed",
            "message": f"Kitchen registration '{kitchen_name}' ({owner_email}) had no dependent records and has been permanently removed."
        }


@router.delete("/kitchen-owners/{kitchen_id}")
@router.delete("/kitchens/{kitchen_id}")
def remove_kitchen_owner(
    kitchen_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Remove or archive a kitchen owner registration.
    Safely archives if business records exist, otherwise permanently deletes unfulfilled test records.
    Strictly prevents deletion/archival of protected legitimate kitchen owners.
    """
    kitchen = db.query(KitchenProfile).filter(
        (KitchenProfile.id == kitchen_id) | (KitchenProfile.user_id == kitchen_id)
    ).first()

    if not kitchen:
        # Check if kitchen_id refers to an orphaned KITCHEN_OWNER user account
        orphaned_user = db.query(User).filter(
            User.id == kitchen_id,
            User.role == UserRole.KITCHEN_OWNER
        ).first()
        if orphaned_user:
            if _is_protected_kitchen_owner(None, orphaned_user):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot remove protected legitimate kitchen owner '{orphaned_user.full_name}' ({orphaned_user.email})."
                )
            result = _execute_orphaned_owner_cleanup(orphaned_user, admin, db)
            db.commit()
            return result

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kitchen owner record not found"
        )

    if _is_protected_kitchen_owner(kitchen, kitchen.user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot remove protected legitimate kitchen owner account '{kitchen.kitchen_name}'."
        )

    try:
        result = _execute_kitchen_removal(kitchen, admin, db)
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except Exception as err:
        db.rollback()
        logger.exception(f"Error removing kitchen owner {kitchen_id}: {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error during removal: {str(err)}"
        )


@router.post("/kitchen-owners/batch-remove")
def batch_remove_kitchen_owners(
    req: BatchRemoveKitchenOwnersRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Admin-only batch removal of selected kitchen owner records.
    Applies identical safety checks per record (archiving if has business records, deleting if test record).
    Strictly protects legitimate accounts from batch removal.
    """
    deleted_count = 0
    archived_count = 0
    errors = []

    for k_id in req.kitchen_ids:
        kitchen = db.query(KitchenProfile).filter(
            (KitchenProfile.id == k_id) | (KitchenProfile.user_id == k_id)
        ).first()

        if not kitchen:
            orphaned_user = db.query(User).filter(
                User.id == k_id,
                User.role == UserRole.KITCHEN_OWNER
            ).first()
            if orphaned_user:
                if _is_protected_kitchen_owner(None, orphaned_user):
                    errors.append(f"Cannot remove protected legitimate kitchen owner ({orphaned_user.email})")
                    continue
                try:
                    _execute_orphaned_owner_cleanup(orphaned_user, admin, db)
                    deleted_count += 1
                except Exception as err:
                    errors.append(f"Failed removing orphaned owner {orphaned_user.email}: {str(err)}")
                continue

            errors.append(f"Kitchen ID {k_id} not found")
            continue

        if kitchen.user_id == admin.id:
            errors.append(f"Cannot delete own kitchen registration ({kitchen.kitchen_name})")
            continue

        if _is_protected_kitchen_owner(kitchen, kitchen.user):
            errors.append(f"Cannot remove protected legitimate kitchen owner ({kitchen.kitchen_name})")
            continue

        try:
            res = _execute_kitchen_removal(kitchen, admin, db)
            if res.get("action") == "archived":
                archived_count += 1
            else:
                deleted_count += 1
        except Exception as err:
            errors.append(f"Failed removing {kitchen.kitchen_name}: {str(err)}")

    db.commit()

    return {
        "success": True,
        "deleted_count": deleted_count,
        "archived_count": archived_count,
        "total_processed": deleted_count + archived_count,
        "processed_count": deleted_count + archived_count,
        "errors": errors,
        "message": f"Batch removal complete: {deleted_count} record(s) permanently removed, {archived_count} record(s) safely archived."
    }



@router.get("/kitchens/{kitchen_id}")
def get_kitchen_detail(
    kitchen_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    kitchen = db.query(KitchenProfile).filter(KitchenProfile.id == kitchen_id).first()
    if not kitchen:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kitchen not found")
    return _format_kitchen(kitchen)


@router.post("/kitchens/{kitchen_id}/approve")
def approve_kitchen(
    kitchen_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    kitchen = db.query(KitchenProfile).filter(KitchenProfile.id == kitchen_id).first()
    if not kitchen:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kitchen not found")
    if kitchen.license:
        from backend.app.services.fssai_service import FssaiService
        from backend.app.models.enums import LicenseStatus
        FssaiService.sync_license_expiration(db, kitchen.license)
        if kitchen.license.status in [LicenseStatus.CORRECTION_REQUIRED, LicenseStatus.REJECTED, LicenseStatus.EXPIRED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot approve kitchen: FSSAI License is not verified (Status: {kitchen.license.status.value if hasattr(kitchen.license.status, 'value') else kitchen.license.status}). License verification must be completed first."
            )
        if kitchen.license.status == LicenseStatus.PENDING_REVIEW:
            kitchen.license.status = LicenseStatus.VERIFIED
            kitchen.license.verification_source = "MANUAL_ADMIN"
            kitchen.license.verified_by_user_id = admin.id
            kitchen.license.verified_at = _utc_now()
            kitchen.license.updated_at = _utc_now()

    kitchen.is_approved = True
    kitchen.is_open = True
    kitchen.approval_status = "APPROVED"
    kitchen.rejection_reason = None
    kitchen.updated_at = _utc_now()
    db._allow_auth_service_update = True
    if kitchen.user:
        kitchen.user.is_verified = True
        kitchen.user.is_active = True

    # Notify kitchen owner
    db.add(Notification(
        user_id=kitchen.user_id,
        title="Kitchen Approved!",
        message=f"Congratulations! Your kitchen '{kitchen.kitchen_name}' has been approved by platform administration. You can now configure your menu and accept orders.",
        event_type="NOTIFICATION_CREATED"
    ))
    db.add(AuditLog(
        user_id=admin.id,
        action="KITCHEN_APPROVED",
        entity_name="KitchenProfile",
        entity_id=kitchen.id,
        details_json=json.dumps({"kitchen_name": kitchen.kitchen_name, "approved_by": admin.email})
    ))

    from backend.app.services.notification_service import NotificationService
    NotificationService.notify_admins(
        db=db,
        event_type="KITCHEN_APPROVED",
        title=f"Kitchen Approved: {kitchen.kitchen_name}",
        message=f"Kitchen '{kitchen.kitchen_name}' was verified and approved by {admin.email}.",
        metadata={"entity_type": "kitchen", "entity_id": kitchen.id, "link": "/admin/kitchen-owners"}
    )

    db.commit()
    db.refresh(kitchen)

    try:
        from backend.app.websockets.connection_manager import ws_manager
        appr_payload = {
            "kitchen_id": kitchen.id,
            "kitchen_name": kitchen.kitchen_name,
            "approval_status": "APPROVED",
            "is_approved": True,
            "is_open": kitchen.is_open,
            "updated_at": kitchen.updated_at.isoformat() if kitchen.updated_at else None,
        }
        ws_manager.publish_event(
            event_type="KITCHEN_APPROVAL_UPDATED",
            data=appr_payload,
            target_user_id=kitchen.user_id,
        )
        ws_manager.publish_event(
            event_type="KITCHEN_APPROVAL_UPDATED",
            data=appr_payload,
            target_kitchen_id=kitchen.id,
        )
        ws_manager.publish_event(
            event_type="KITCHEN_APPROVAL_UPDATED",
            data=appr_payload,
            target_role="ADMIN",
        )
    except Exception as ws_err:
        logger.warning(f"Error publishing real-time kitchen approval event: {ws_err}")

    try:
        if kitchen.user and kitchen.user.email:
            email_service.send_kitchen_approval_email_sync(
                to_email=kitchen.user.email,
                kitchen_name=kitchen.kitchen_name,
                approved=True
            )
    except Exception as e:
        logger.warning(f"Failed to send kitchen approval email to {kitchen.user.email if kitchen.user else ''}: {e}")

    return _format_kitchen(kitchen)


@router.post("/kitchens/{kitchen_id}/reactivate")
def reactivate_kitchen(
    kitchen_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Reactivate a suspended or unapproved kitchen."""
    return approve_kitchen(kitchen_id=kitchen_id, admin=admin, db=db)


@router.post("/kitchens/{kitchen_id}/reject")
def reject_kitchen(
    kitchen_id: str,
    req: RejectionRequest = RejectionRequest(),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    kitchen = db.query(KitchenProfile).filter(KitchenProfile.id == kitchen_id).first()
    if not kitchen:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kitchen not found")
    kitchen.is_approved = False
    kitchen.approval_status = "REJECTED"
    kitchen.rejection_reason = req.reason
    kitchen.updated_at = _utc_now()

    # Notify kitchen owner
    db.add(Notification(
        user_id=kitchen.user_id,
        title="Kitchen Application Update",
        message=f"Your kitchen application for '{kitchen.kitchen_name}' was rejected. Reason: {req.reason}",
        event_type="NOTIFICATION_CREATED"
    ))
    db.add(AuditLog(
        user_id=admin.id,
        action="KITCHEN_REJECTED",
        entity_name="KitchenProfile",
        entity_id=kitchen.id,
        details_json=json.dumps({"kitchen_name": kitchen.kitchen_name, "reason": req.reason, "rejected_by": admin.email})
    ))

    from backend.app.services.notification_service import NotificationService
    NotificationService.notify_admins(
        db=db,
        event_type="KITCHEN_REJECTED",
        title=f"Kitchen Rejected: {kitchen.kitchen_name}",
        message=f"Kitchen '{kitchen.kitchen_name}' was rejected by {admin.email}. Reason: {req.reason or 'Not specified'}",
        metadata={"entity_type": "kitchen", "entity_id": kitchen.id, "link": "/admin/kitchen-owners"}
    )

    db.commit()
    db.refresh(kitchen)

    try:
        from backend.app.websockets.connection_manager import ws_manager
        rej_payload = {
            "kitchen_id": kitchen.id,
            "kitchen_name": kitchen.kitchen_name,
            "approval_status": "REJECTED",
            "is_approved": False,
            "rejection_reason": req.reason,
            "updated_at": kitchen.updated_at.isoformat() if kitchen.updated_at else None,
        }
        ws_manager.publish_event(
            event_type="KITCHEN_APPROVAL_UPDATED",
            data=rej_payload,
            target_user_id=kitchen.user_id,
        )
        ws_manager.publish_event(
            event_type="KITCHEN_APPROVAL_UPDATED",
            data=rej_payload,
            target_kitchen_id=kitchen.id,
        )
        ws_manager.publish_event(
            event_type="KITCHEN_APPROVAL_UPDATED",
            data=rej_payload,
            target_role="ADMIN",
        )
    except Exception as ws_err:
        logger.warning(f"Error publishing real-time kitchen rejection event: {ws_err}")

    try:
        if kitchen.user and kitchen.user.email:
            email_service.send_kitchen_approval_email_sync(
                to_email=kitchen.user.email,
                kitchen_name=kitchen.kitchen_name,
                approved=False,
                reason=req.reason
            )
    except Exception as e:
        logger.warning(f"Failed to send kitchen rejection email to {kitchen.user.email if kitchen.user else ''}: {e}")

    return _format_kitchen(kitchen)


@router.post("/kitchens/{kitchen_id}/suspend")
def suspend_kitchen(
    kitchen_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    kitchen = db.query(KitchenProfile).filter(KitchenProfile.id == kitchen_id).first()
    if not kitchen:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kitchen not found")
    kitchen.is_approved = False
    kitchen.approval_status = "SUSPENDED"
    kitchen.updated_at = _utc_now()

    db.add(Notification(
        user_id=kitchen.user_id,
        title="Kitchen Suspended",
        message=f"Your kitchen '{kitchen.kitchen_name}' has been temporarily suspended by administration.",
        event_type="NOTIFICATION_CREATED"
    ))
    db.add(AuditLog(
        user_id=admin.id,
        action="KITCHEN_SUSPENDED",
        entity_name="KitchenProfile",
        entity_id=kitchen.id,
        details_json=json.dumps({"kitchen_name": kitchen.kitchen_name, "suspended_by": admin.email})
    ))
    db.commit()
    db.refresh(kitchen)

    try:
        from backend.app.websockets.connection_manager import ws_manager
        susp_payload = {
            "kitchen_id": kitchen.id,
            "kitchen_name": kitchen.kitchen_name,
            "approval_status": "SUSPENDED",
            "is_approved": False,
            "updated_at": kitchen.updated_at.isoformat() if kitchen.updated_at else None,
        }
        ws_manager.publish_event(
            event_type="KITCHEN_APPROVAL_UPDATED",
            data=susp_payload,
            target_user_id=kitchen.user_id,
        )
        ws_manager.publish_event(
            event_type="KITCHEN_APPROVAL_UPDATED",
            data=susp_payload,
            target_kitchen_id=kitchen.id,
        )
        ws_manager.publish_event(
            event_type="KITCHEN_APPROVAL_UPDATED",
            data=susp_payload,
            target_role="ADMIN",
        )
    except Exception as ws_err:
        logger.warning(f"Error publishing real-time kitchen suspension event: {ws_err}")

    return _format_kitchen(kitchen)




# ── 4. Menu Items ─────────────────────────────────────────────────────────────
@router.get("/menu")
def get_menu_items(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None),
    kitchen_id: Optional[str] = Query(None),
    available: Optional[bool] = Query(None),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    q = db.query(MenuItem)
    if search:
        term = f"%{search.lower()}%"
        q = q.filter(func.lower(MenuItem.name).like(term) | func.lower(MenuItem.category).like(term))
    if kitchen_id:
        q = q.filter(MenuItem.kitchen_id == kitchen_id)
    if available is not None:
        q = q.filter(MenuItem.is_available == available)

    total = q.count()
    items = q.order_by(MenuItem.created_at.desc()).offset(skip).limit(limit).all()
    formatted = []
    for item in items:
        formatted.append({
            "id": item.id,
            "name": item.name,
            "description": item.description,
            "price": item.price,
            "is_available": item.is_available,
            "created_at": item.created_at.isoformat() if item.created_at else _utc_now().isoformat(),
            "kitchen": {
                "id": item.kitchen.id if item.kitchen else None,
                "kitchen_name": item.kitchen.kitchen_name if item.kitchen else "Unknown",
            },
        })
    return {"items": formatted, "total": total, "skip": skip, "limit": limit}


# ── 5. Orders & Payments ──────────────────────────────────────────────────────
@router.get("/orders")
def get_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None),
    kitchen_id: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    q = db.query(Order)
    if status:
        q = q.filter(Order.status == status)
    if customer_id:
        q = q.filter(Order.customer_id == customer_id)
    if kitchen_id:
        q = q.filter(Order.kitchen_id == kitchen_id)

    total = q.count()
    orders = q.order_by(Order.created_at.desc()).offset(skip).limit(limit).all()
    formatted = []
    for o in orders:
        cust = db.query(User).filter(User.id == o.customer_id).first()
        kitch = db.query(KitchenProfile).filter(KitchenProfile.id == o.kitchen_id).first()
        formatted.append({
            "id": o.id,
            "status": o.status.value if hasattr(o.status, "value") else str(o.status),
            "total_amount": float(o.total_amount),
            "ordered_at": o.created_at.isoformat() if o.created_at else _utc_now().isoformat(),
            "customer": {
                "id": cust.id if cust else "",
                "email": cust.email if cust else "",
                "first_name": (cust.full_name or "").split(" ")[0] if cust else "",
                "last_name": (cust.full_name or "").split(" ")[1] if cust and len((cust.full_name or "").split(" ")) > 1 else "",
            } if cust else None,
            "kitchen": {
                "id": kitch.id if kitch else "",
                "kitchen_name": kitch.kitchen_name if kitch else "Unknown",
            } if kitch else None,
            "payment": {
                "id": o.payments[0].id if (hasattr(o, "payments") and o.payments) else "",
                "amount": float(o.payments[0].amount) if (hasattr(o, "payments") and o.payments) else float(o.total_amount),
                "status": o.payments[0].status.value if (hasattr(o, "payments") and o.payments and hasattr(o.payments[0].status, "value")) else "SUCCESS",
                "payment_method": getattr(o.payments[0], "payment_provider", "COD") if (hasattr(o, "payments") and o.payments) else "COD",
            } if (hasattr(o, "payments") and o.payments) else None,
        })
    return {"orders": formatted, "total": total, "skip": skip, "limit": limit}


@router.get("/payments")
def get_payments(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    q = db.query(Payment)
    if status:
        q = q.filter(Payment.status == status)
    total = q.count()
    payments = q.order_by(Payment.created_at.desc()).offset(skip).limit(limit).all()
    formatted = []
    for p in payments:
        formatted.append({
            "id": p.id,
            "amount": float(p.amount),
            "status": p.status.value if hasattr(p.status, "value") else str(p.status),
            "payment_method": getattr(p, "payment_provider", "COD"),
            "transaction_id": getattr(p, "transaction_reference", p.id),
            "created_at": p.created_at.isoformat() if p.created_at else _utc_now().isoformat(),
            "paid_at": p.created_at.isoformat() if (p.status == PaymentStatus.SUCCESS or getattr(p.status, "value", str(p.status)) in ["SUCCESS", "COMPLETED"]) else None,
            "order": {
                "id": p.order.id if p.order else "",
                "order_number": getattr(p.order, "order_number", "") if p.order else "",
            } if p.order else None,
        })
    return {"payments": formatted, "total": total, "skip": skip, "limit": limit}


@router.delete("/payments/{payment_id}")
def delete_or_archive_payment(
    payment_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Payments must remain auditable:
    - Never allow permanent deletion of completed/successful payment transactions.
    - If administrative archival is requested, preserve financial history in ledger and log audit trail.
    """
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment transaction not found")

    status_str = payment.status.value if hasattr(payment.status, "value") else str(payment.status)
    if status_str.upper() in ["COMPLETED", "SUCCESS", "PAID"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Completed payment transactions cannot be permanently deleted. Financial records must remain intact for auditing."
        )

    db.add(AuditLog(
        user_id=admin.id,
        action="PAYMENT_ARCHIVED",
        entity_name="Payment",
        entity_id=payment.id,
        details_json=json.dumps({
            "payment_id": payment.id,
            "amount": float(payment.amount),
            "status": status_str,
            "archived_by": admin.email,
            "note": "Payment transaction archived from active view; preserved in financial ledger"
        })
    ))
    db.commit()
    return {
        "success": True,
        "action": "archived",
        "message": f"Payment #{payment.id[:8]} archived. Financial transaction records preserved for auditing."
    }



# ── 6. Inventory & Waste ──────────────────────────────────────────────────────
@router.get("/inventory")
def get_inventory(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    kitchen_id: Optional[str] = Query(None),
    low_stock: Optional[bool] = Query(None),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    q = db.query(Inventory)
    if kitchen_id:
        q = q.filter(Inventory.kitchen_id == kitchen_id)
    if low_stock:
        q = q.filter(Inventory.status == InventoryStatus.LOW_STOCK)

    total = q.count()
    items = q.order_by(Inventory.last_updated.desc()).offset(skip).limit(limit).all()
    formatted = []
    for inv in items:
        ing = inv.ingredient
        kitch = inv.kitchen
        qty = float(inv.quantity)
        min_qty = float(getattr(ing, "minimum_stock_threshold", 10.0) or 10.0) if ing else 10.0
        val = KitchenService.get_ingredient_valuation(db, inv.kitchen_id, inv.ingredient_id, qty)
        formatted.append({
            "id": inv.id,
            "kitchen_name": kitch.kitchen_name if kitch else "Unknown",
            "ingredient_name": ing.name if ing else "Unknown",
            "quantity": qty,
            "quantity_on_hand": qty,
            "min_quantity": min_qty,
            "max_quantity": None,
            "unit_cost": val["unit_cost"],
            "cost_available": val["cost_available"],
            "stock_value": val["stock_value"],
            "unit": inv.unit,
            "status": inv.status.value if hasattr(inv.status, "value") else str(inv.status),
            "last_updated": inv.last_updated.isoformat() if inv.last_updated else _utc_now().isoformat(),
            "last_restocked_at": inv.last_updated.isoformat() if inv.last_updated else None,
            "kitchen": {
                "id": kitch.id if kitch else "",
                "kitchen_name": kitch.kitchen_name if kitch else "Unknown",
            } if kitch else None,
            "ingredient": {
                "id": ing.id if ing else "",
                "name": ing.name if ing else "Unknown",
                "unit": inv.unit,
            } if ing else None,
        })
    return {"inventory": formatted, "total": total, "skip": skip, "limit": limit}


@router.get("/waste")
def get_waste_records(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    kitchen_id: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    q = db.query(WasteRecord)
    if kitchen_id:
        q = q.filter(WasteRecord.kitchen_id == kitchen_id)
    total = q.count()
    records = q.order_by(WasteRecord.created_at.desc()).offset(skip).limit(limit).all()
    
    # Calculate real totals for analytics summary
    total_cost_val = db.query(func.coalesce(func.sum(WasteRecord.estimated_cost), 0.0))
    total_qty_val = db.query(func.coalesce(func.sum(WasteRecord.quantity), 0.0))
    if kitchen_id:
        total_cost_val = total_cost_val.filter(WasteRecord.kitchen_id == kitchen_id)
        total_qty_val = total_qty_val.filter(WasteRecord.kitchen_id == kitchen_id)
    summary_total_cost = float(total_cost_val.scalar() or 0.0)
    summary_total_qty = float(total_qty_val.scalar() or 0.0)

    now_iso = datetime.now(timezone.utc).isoformat()
    formatted = []
    for w in records:
        ing = w.ingredient
        kitch = w.kitchen
        item_name = ing.name if ing else (w.menu_item_name or "N/A")
        item_unit = ing.unit if ing else (w.unit or "")
        cost_val = float(w.estimated_cost) if w.estimated_cost is not None else None
        cost_avail = (cost_val is not None and cost_val > 0.0)
        dt_str = w.created_at.isoformat() if w.created_at else now_iso
        
        formatted.append({
            "id": w.id,
            "kitchen_id": w.kitchen_id,
            "kitchen_name": kitch.kitchen_name if kitch else "Unknown",
            "kitchen": {
                "id": kitch.id if kitch else w.kitchen_id,
                "kitchen_name": kitch.kitchen_name if kitch else "Unknown",
            } if kitch else None,
            "ingredient_id": w.ingredient_id,
            "ingredient_name": item_name,
            "ingredient": {
                "id": ing.id if ing else (w.ingredient_id or ""),
                "name": item_name,
                "unit": item_unit,
            } if (ing or w.ingredient_id) else None,
            "menu_item_id": w.menu_item_id,
            "menu_item_name": w.menu_item_name,
            "portions_wasted": float(w.portions_wasted) if w.portions_wasted is not None else None,
            "quantity": float(w.quantity or 0.0),
            "unit": w.unit or "",
            "reason": w.reason,
            "recorded_by": w.recorded_by,
            "cost": cost_val,
            "estimated_cost": cost_val,
            "cost_available": cost_avail,
            "recorded_at": dt_str,
            "created_at": dt_str,
            "source_event": w.source_event or "MANUAL",
        })
    return {
        "waste_records": formatted,
        "total": total,
        "skip": skip,
        "limit": limit,
        "summary": {
            "total_cost": round(summary_total_cost, 2),
            "total_quantity": round(summary_total_qty, 2),
            "total_records": total,
        }
    }


# ── 7. Reviews, Promotions, & ML Demand ────────────────────────────────────────
@router.get("/reviews")
def get_reviews(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    kitchen_id: Optional[str] = Query(None),
    min_rating: Optional[float] = Query(None),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    q = db.query(Review)
    if kitchen_id:
        q = q.filter(Review.kitchen_id == kitchen_id)
    if min_rating is not None:
        q = q.filter(Review.rating >= min_rating)
    total = q.count()
    revs = q.order_by(Review.created_at.desc()).offset(skip).limit(limit).all()
    now_iso = datetime.now(timezone.utc).isoformat()
    formatted = []
    for r in revs:
        cust = r.customer
        kitch = r.kitchen
        ord_obj = r.order
        mi_obj = r.menu_item
        first_n = (cust.full_name or "").split(" ")[0] if cust else "Anonymous"
        last_n = (cust.full_name or "").split(" ")[1] if cust and len((cust.full_name or "").split(" ")) > 1 else ""
        formatted.append({
            "id": r.id,
            "rating": r.rating,
            "comment": r.comment,
            "created_at": r.created_at.isoformat() if r.created_at else now_iso,
            "customer": {
                "id": cust.id if cust else "",
                "name": cust.full_name if cust else "Anonymous",
            },
            "user": {
                "id": cust.id if cust else "",
                "email": cust.email if cust else "",
                "first_name": first_n,
                "last_name": last_n,
            } if cust else None,
            "kitchen": {
                "id": kitch.id if kitch else "",
                "name": kitch.kitchen_name if kitch else "Unknown",
                "kitchen_name": kitch.kitchen_name if kitch else "Unknown",
            },
            "order_id": r.order_id,
            "order_number": ord_obj.order_number if ord_obj else None,
            "order": {
                "id": ord_obj.id if ord_obj else "",
                "order_number": ord_obj.order_number if ord_obj else "",
            } if ord_obj else None,
            "menu_item_id": r.menu_item_id,
            "menu_item_name": mi_obj.name if mi_obj else None,
            "menu_item": {
                "id": mi_obj.id if mi_obj else "",
                "name": mi_obj.name if mi_obj else "",
            } if mi_obj else None,
            "is_visible": True,
        })
    return {"reviews": formatted, "total": total, "skip": skip, "limit": limit}


@router.get("/promotions")
def get_promotions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    q = db.query(Promotion)
    if active is not None:
        q = q.filter(Promotion.is_active == active)
    if search:
        search_term = f"%{search}%"
        q = q.filter(
            or_(
                Promotion.code.ilike(search_term),
                Promotion.title.ilike(search_term),
                Promotion.description.ilike(search_term)
            )
        )
    total = q.count()
    promos = q.order_by(Promotion.created_at.desc()).offset(skip).limit(limit).all()
    formatted = []
    for p in promos:
        discount_pct = getattr(p, "discount_percentage", None) or getattr(p, "discount_percent", 0.0) or 0.0
        min_amount = getattr(p, "minimum_order_amount", None) or getattr(p, "min_order_amount", 0.0) or 0.0
        max_discount = getattr(p, "max_discount_amount", None)
        u_limit = getattr(p, "usage_limit", None)
        u_count = getattr(p, "usage_count", 0) or 0
        pu_limit = getattr(p, "per_user_limit", 1) or 1
        expires = getattr(p, "end_date", None) or getattr(p, "valid_until", None)
        starts = getattr(p, "start_date", None) or getattr(p, "valid_from", None)
        p_type = "PERCENTAGE" if discount_pct > 0 else "FIXED_AMOUNT"
        d_val = discount_pct if discount_pct > 0 else float(p.discount_amount or 0.0)
        formatted.append({
            "id": p.id,
            "code": p.code,
            "title": p.title or p.code,
            "description": p.description,
            "promotion_type": p_type,
            "discount_value": float(d_val),
            "discount_percent": float(discount_pct),
            "discount_percentage": float(discount_pct),
            "discount_amount": float(p.discount_amount or 0.0),
            "min_order_amount": float(min_amount),
            "minimum_order_amount": float(min_amount),
            "max_discount_amount": float(max_discount) if max_discount is not None else None,
            "usage_limit": u_limit,
            "usage_count": u_count,
            "per_user_limit": pu_limit,
            "is_active": p.is_active,
            "starts_at": starts.isoformat() if starts else _utc_now().isoformat(),
            "expires_at": expires.isoformat() if expires else (_utc_now() + timedelta(days=30)).isoformat(),
            "created_at": p.created_at.isoformat() if p.created_at else _utc_now().isoformat(),
        })
    return {"promotions": formatted, "total": total, "skip": skip, "limit": limit}


@router.post("/promotions", status_code=status.HTTP_201_CREATED)
def create_promotion(
    req: PromotionCreateRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    code_clean = req.code.strip().upper()
    existing = db.query(Promotion).filter(Promotion.code == code_clean).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Promotion code '{code_clean}' already exists")
    promo = Promotion(
        code=code_clean,
        title=req.title.strip() if req.title else code_clean,
        description=req.description,
        discount_percentage=req.discount_percent,
        discount_amount=req.discount_amount,
        max_discount_amount=req.max_discount_amount,
        minimum_order_amount=req.min_order_amount,
        usage_limit=req.usage_limit,
        usage_count=0,
        per_user_limit=req.per_user_limit,
        is_active=req.is_active,
        start_date=req.valid_from or _utc_now(),
        end_date=req.valid_until or (_utc_now() + timedelta(days=30)),
    )
    db.add(promo)

    from backend.app.services.notification_service import NotificationService
    NotificationService.notify_admins(
        db=db,
        event_type="SYSTEM_EVENT",
        title=f"New Promotion Active: {promo.code}",
        message=f"Promotion '{promo.title}' code '{promo.code}' ({promo.discount_percentage}% off) has been created.",
        metadata={"entity_type": "promotion", "entity_id": promo.id, "link": "/admin/promotions"}
    )

    db.commit()
    db.refresh(promo)
    return {
        "id": promo.id,
        "code": promo.code,
        "title": promo.title,
        "description": promo.description,
        "promotion_type": "PERCENTAGE" if promo.discount_percentage > 0 else "FIXED_AMOUNT",
        "discount_value": float(promo.discount_percentage if promo.discount_percentage > 0 else promo.discount_amount),
        "discount_percent": float(promo.discount_percentage),
        "discount_percentage": float(promo.discount_percentage),
        "discount_amount": float(promo.discount_amount),
        "min_order_amount": float(promo.minimum_order_amount),
        "minimum_order_amount": float(promo.minimum_order_amount),
        "max_discount_amount": float(promo.max_discount_amount) if promo.max_discount_amount is not None else None,
        "usage_limit": promo.usage_limit,
        "usage_count": promo.usage_count,
        "per_user_limit": promo.per_user_limit,
        "is_active": promo.is_active,
    }


@router.put("/promotions/{promo_id}")
def update_promotion(
    promo_id: str,
    req: PromotionUpdateRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    promo = db.query(Promotion).filter(Promotion.id == promo_id).first()
    if not promo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion not found")
    
    if req.title is not None:
        promo.title = req.title.strip()
    if req.description is not None:
        promo.description = req.description.strip()
    if req.discount_percent is not None:
        promo.discount_percentage = req.discount_percent
    if req.discount_amount is not None:
        promo.discount_amount = req.discount_amount
    if req.max_discount_amount is not None:
        promo.max_discount_amount = req.max_discount_amount
    if req.min_order_amount is not None:
        promo.minimum_order_amount = req.min_order_amount
    if req.usage_limit is not None:
        promo.usage_limit = req.usage_limit
    if req.per_user_limit is not None:
        promo.per_user_limit = req.per_user_limit
    if req.is_active is not None:
        promo.is_active = req.is_active
    if req.valid_from is not None:
        promo.start_date = req.valid_from
    if req.valid_until is not None:
        promo.end_date = req.valid_until

    db.commit()
    db.refresh(promo)
    return {
        "id": promo.id,
        "code": promo.code,
        "title": promo.title,
        "description": promo.description,
        "discount_percent": float(promo.discount_percentage),
        "discount_amount": float(promo.discount_amount),
        "min_order_amount": float(promo.minimum_order_amount),
        "max_discount_amount": float(promo.max_discount_amount) if promo.max_discount_amount is not None else None,
        "usage_limit": promo.usage_limit,
        "usage_count": promo.usage_count,
        "per_user_limit": promo.per_user_limit,
        "is_active": promo.is_active,
    }


@router.patch("/promotions/{promo_id}/toggle")
def toggle_promotion_status(
    promo_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    promo = db.query(Promotion).filter(Promotion.id == promo_id).first()
    if not promo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion not found")
    promo.is_active = not promo.is_active
    db.commit()
    db.refresh(promo)
    return {
        "id": promo.id,
        "code": promo.code,
        "is_active": promo.is_active,
        "message": f"Promotion '{promo.code}' is now {'active' if promo.is_active else 'inactive'}"
    }


@router.delete("/promotions/{promo_id}")
def delete_promotion(
    promo_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    promo = db.query(Promotion).filter(Promotion.id == promo_id).first()
    if not promo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion not found")
    
    # Check if historical orders used this promotion
    historical_usage = db.query(Order).filter(Order.promotion_code == promo.code).first()
    if historical_usage:
        # Soft deactivate to protect historical orders
        promo.is_active = False
        db.commit()
        return {
            "message": f"Promotion '{promo.code}' was referenced by historical orders and has been safely deactivated (archived).",
            "archived": True,
            "is_active": False
        }
    
    code = promo.code
    db.delete(promo)
    db.commit()
    return {
        "message": f"Promotion '{code}' has been permanently deleted.",
        "deleted": True
    }


@router.post("/promotions/{promo_id}/send-campaign")
def send_promotion_campaign(
    promo_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    promo = db.query(Promotion).filter(Promotion.id == promo_id).first()
    if not promo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion not found")
    if not promo.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot send campaign for an inactive promotion")

    # Real customers from DB
    customers = db.query(User).filter(
        User.role == UserRole.CUSTOMER,
        User.is_active == True
    ).all()

    discount_text = f"{promo.discount_percentage:.0f}% OFF" if promo.discount_percentage > 0 else f"₹{promo.discount_amount:.2f} OFF"
    if promo.max_discount_amount:
        discount_text += f" (Up to ₹{promo.max_discount_amount:.2f})"
    min_order_text = f"Minimum Order: ₹{promo.minimum_order_amount:.2f}" if promo.minimum_order_amount > 0 else "No minimum order amount"
    expiry_text = f"Valid until: {promo.end_date.strftime('%B %d, %Y')}" if promo.end_date else "Limited time offer"

    sent_count = 0
    for cust in customers:
        if cust.email:
            try:
                email_service.send_promotion_campaign_email_sync(
                    to_email=cust.email,
                    promo_code=promo.code,
                    title=promo.title or promo.code,
                    discount_text=discount_text,
                    expiry_text=expiry_text,
                    min_order_text=min_order_text,
                )
                sent_count += 1
            except Exception as e:
                logger.warning(f"Failed to dispatch campaign email to {cust.email}: {e}")

    return {
        "status": "success",
        "promo_code": promo.code,
        "dispatched_count": sent_count,
        "message": f"Promotional campaign for '{promo.code}' dispatched to {sent_count} active customers."
    }



@router.get("/demand-predictions")
def get_demand_predictions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    kitchen_id: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    q = db.query(DemandPrediction)
    if kitchen_id:
        q = q.filter(DemandPrediction.kitchen_id == kitchen_id)
    total = q.count()
    preds = q.order_by(DemandPrediction.prediction_date.desc()).offset(skip).limit(limit).all()
    formatted = []
    for pred in preds:
        kitch = pred.kitchen
        item = pred.menu_item
        formatted.append({
            "id": pred.id,
            "prediction_date": pred.prediction_date.isoformat() if hasattr(pred.prediction_date, "isoformat") else str(pred.prediction_date),
            "predicted_demand": float(pred.predicted_orders),
            "confidence_score": float(pred.confidence_score or 0.85),
            "model_version": pred.model_version,
            "kitchen": {
                "id": kitch.id if kitch else "",
                "kitchen_name": kitch.kitchen_name if kitch else "Unknown",
            },
            "menu_item": {
                "id": item.id if item else "",
                "name": item.name if item else "Unknown",
                "price": float(item.price) if item else 0.0,
            },
        })
    return {"predictions": formatted, "total": total, "skip": skip, "limit": limit}


# ── 8. Analytics & Audit Logs ─────────────────────────────────────────────────
@router.get("/analytics")
def get_analytics(
    scenario: str = Query("production", description="Filter: 'production' (default, excludes test orders) or 'test_scenario' (only test orders)"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    today = datetime.now(timezone.utc).date()
    orders_over_time = []
    revenue_over_time = []
    
    # Filter based on scenario:
    # "production": only real orders (is_test == False and order_number NOT LIKE 'TEST-%')
    # "test_scenario": only test scenario orders (is_test == True or order_number LIKE 'TEST-%')
    is_test_filter = (Order.is_test == True) if scenario == "test_scenario" else (Order.is_test == False)

    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)

        count = db.query(func.count(Order.id)).filter(
            Order.created_at >= day_start, Order.created_at < day_end,
            is_test_filter
        ).scalar() or 0
        rev = db.query(func.sum(Order.total_amount)).filter(
            Order.created_at >= day_start, Order.created_at < day_end,
            is_test_filter,
            Order.status == OrderStatus.DELIVERED,
            Order.payment_status == PaymentStatus.SUCCESS,
            ~Order.status.in_([OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.REFUNDED]),
            Order.payment_status != PaymentStatus.REFUNDED
        ).scalar() or 0.0

        orders_over_time.append({"date": day.strftime("%b %d"), "count": count})
        revenue_over_time.append({"date": day.strftime("%b %d"), "revenue": float(rev)})

    # Order status breakdown
    status_counts = db.query(Order.status, func.count(Order.id)).filter(is_test_filter).group_by(Order.status).all()
    order_status = [{"status": s.value if hasattr(s, "value") else str(s), "count": c} for s, c in status_counts]

    # Kitchen activity
    kitchen_counts = db.query(KitchenProfile.kitchen_name, func.count(Order.id)).join(
        Order, KitchenProfile.id == Order.kitchen_id
    ).filter(is_test_filter).group_by(KitchenProfile.kitchen_name).limit(5).all()
    kitchen_activity = [{"kitchen": name, "orders": count} for name, count in kitchen_counts]

    # Popular items
    item_counts = db.query(MenuItem.name, func.sum(OrderItem.quantity)).join(
        OrderItem, MenuItem.id == OrderItem.menu_item_id
    ).join(
        Order, Order.id == OrderItem.order_id
    ).filter(is_test_filter).group_by(MenuItem.name).order_by(func.sum(OrderItem.quantity).desc()).limit(5).all()
    popular_items = [{"item": name, "ordered": int(qty or 0)} for name, qty in item_counts]

    total_inv = db.query(func.count(Inventory.id)).scalar() or 0
    low_stock = db.query(func.count(Inventory.id)).filter(Inventory.status == InventoryStatus.LOW_STOCK).scalar() or 0

    return {
        "scenario": scenario,
        "orders_over_time": orders_over_time,
        "revenue_over_time": revenue_over_time,
        "order_status": order_status,
        "kitchen_activity": kitchen_activity,
        "popular_items": popular_items,
        "customer_growth": orders_over_time,
        "inventory_status": {"total": total_inv, "low_stock": low_stock},
        "waste_trends": [],
    }


@router.get("/audit-logs")
def get_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    q = db.query(AuditLog)
    if user_id:
        q = q.filter(AuditLog.user_id == user_id)
    if action:
        q = q.filter(AuditLog.action == action)
    total = q.count()
    logs = q.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit).all()
    formatted = []
    for l in logs:
        u = db.query(User).filter(User.id == l.user_id).first()
        formatted.append({
            "id": l.id,
            "action": l.action,
            "resource_type": l.entity_name,
            "resource_id": l.entity_id,
            "details": json.loads(l.details_json) if l.details_json else {},
            "ip_address": l.ip_address,
            "created_at": l.created_at.isoformat() if l.created_at else _utc_now().isoformat(),
            "user": {
                "id": u.id if u else "",
                "email": u.email if u else "System",
                "first_name": (u.full_name or "").split(" ")[0] if u else "System",
                "last_name": (u.full_name or "").split(" ")[1] if u and len((u.full_name or "").split(" ")) > 1 else "",
            } if u else None,
        })
    return {"logs": formatted, "total": total, "skip": skip, "limit": limit}


# ── 9. Admin Profile ──────────────────────────────────────────────────────────
@router.get("/profile")
def get_admin_profile(
    admin: User = Depends(require_admin),
):
    return _format_user(admin)


@router.put("/profile")
def update_admin_profile(
    req: AdminProfileUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    if req.full_name is not None:
        admin.full_name = req.full_name
    if req.phone_number is not None:
        admin.phone_number = req.phone_number
    db.commit()
    db.refresh(admin)
    return _format_user(admin)


# ── 10. Admin Notifications ───────────────────────────────────────────────────
@router.get("/notifications")
def get_admin_notifications(
    category: Optional[str] = Query(None),
    tab: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Retrieve platform alerts and requests for administrators with categorized filtering."""
    from backend.app.services.notification_service import NotificationService, get_event_category

    # Run idempotent sync from real database events so platform history is immediately available
    NotificationService.sync_admin_notifications_from_platform(db, admin_id=admin.id)

    # Base query for this specific admin (guarantees isolation across admins)
    base_q = db.query(Notification).filter(Notification.user_id == admin.id)

    # Fetch all for category counts
    all_notifs = base_q.order_by(Notification.created_at.desc()).all()

    total_count = len(all_notifs)
    unread_count = sum(1 for n in all_notifs if not n.is_read)
    read_count = sum(1 for n in all_notifs if n.is_read)

    counts_by_tab = {
        "all": total_count,
        "unread": unread_count,
        "read": read_count,
        "kitchen": 0,
        "orders": 0,
        "payments": 0,
        "inventory": 0,
        "system": 0,
    }

    categorized_items = []
    for n in all_notifs:
        cat = get_event_category(n.event_type)
        cat_key = cat.lower()
        if cat_key in counts_by_tab:
            counts_by_tab[cat_key] += 1

        meta = {}
        if n.metadata_json:
            try:
                meta = json.loads(n.metadata_json)
            except Exception:
                meta = {}

        link = meta.get("link")
        if not link:
            if cat == "KITCHEN":
                link = "/admin/kitchen-owners"
            elif cat == "ORDERS":
                link = "/admin/orders"
            elif cat == "PAYMENTS":
                link = "/admin/payments"
            elif cat == "INVENTORY":
                link = "/admin/inventory"
            elif cat == "SYSTEM":
                link = "/admin/promotions" if meta.get("entity_type") == "promotion" else "/admin/settings"
            else:
                link = "/admin/dashboard"

        categorized_items.append({
            "id": n.id,
            "user_id": n.user_id,
            "title": n.title,
            "message": n.message,
            "event_type": n.event_type,
            "notification_type": n.event_type,
            "category": cat,
            "is_read": n.is_read,
            "metadata": meta,
            "link": link,
            "created_at": n.created_at.isoformat() if n.created_at else _utc_now().isoformat()
        })

    # Apply active filter
    active_filter = (category or tab or "ALL").upper().strip()
    filtered_items = categorized_items

    if active_filter == "UNREAD":
        filtered_items = [item for item in categorized_items if not item["is_read"]]
    elif active_filter == "READ":
        filtered_items = [item for item in categorized_items if item["is_read"]]
    elif active_filter in ["KITCHEN", "KITCHEN_APPROVALS", "KITCHEN APPROVALS"]:
        filtered_items = [item for item in categorized_items if item["category"] == "KITCHEN"]
    elif active_filter == "ORDERS":
        filtered_items = [item for item in categorized_items if item["category"] == "ORDERS"]
    elif active_filter == "PAYMENTS":
        filtered_items = [item for item in categorized_items if item["category"] == "PAYMENTS"]
    elif active_filter == "INVENTORY":
        filtered_items = [item for item in categorized_items if item["category"] == "INVENTORY"]
    elif active_filter == "SYSTEM":
        filtered_items = [item for item in categorized_items if item["category"] == "SYSTEM"]

    paged_items = filtered_items[offset:offset + limit]

    return {
        "notifications": paged_items,
        "unread_count": unread_count,
        "read_count": read_count,
        "total_count": total_count,
        "counts_by_tab": counts_by_tab
    }


@router.get("/notifications/unread-count")
def get_admin_unread_notification_count(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Fast query for admin unread notification badge."""
    count = db.query(Notification).filter(
        Notification.user_id == admin.id,
        Notification.is_read == False
    ).count()
    return {"unread_count": count}


@router.put("/notifications/read-all")
@router.patch("/notifications/read-all")
def mark_all_admin_notifications_read(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Mark all unread admin alerts as read."""
    count = db.query(Notification).filter(
        Notification.user_id == admin.id,
        Notification.is_read == False
    ).update({"is_read": True})
    db.commit()
    return {"status": "success", "marked_read_count": count}


@router.put("/notifications/{notification_id}/read")
@router.patch("/notifications/{notification_id}/read")
def mark_admin_notification_read(
    notification_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Mark a specific admin alert as read."""
    notif = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == admin.id
    ).first()
    if not notif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    notif.is_read = True
    db.commit()
    return {"status": "success", "id": notification_id, "is_read": True}


@router.put("/notifications/{notification_id}/unread")
@router.patch("/notifications/{notification_id}/unread")
def mark_admin_notification_unread(
    notification_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Mark a specific admin alert as unread."""
    notif = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == admin.id
    ).first()
    if not notif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    notif.is_read = False
    db.commit()
    return {"status": "success", "id": notification_id, "is_read": False}


@router.delete("/notifications/clear-read")
@router.post("/notifications/clear-read")
def clear_read_admin_notifications(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Safely clear only read notifications. Never deletes unread notifications."""
    count = db.query(Notification).filter(
        Notification.user_id == admin.id,
        Notification.is_read == True
    ).delete(synchronize_session=False)
    db.commit()
    return {"status": "success", "cleared_count": count}


@router.delete("/notifications/{notification_id}")
def delete_admin_notification(
    notification_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Delete an individual notification."""
    notif = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == admin.id
    ).first()
    if not notif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    db.delete(notif)
    db.commit()
    return {"status": "success", "deleted_id": notification_id}


# ── 11. Admin Platform Settings ───────────────────────────────────────────────
class AdminSettingsPayload(BaseModel):
    app_name: Optional[str] = None
    email_provider: Optional[str] = None
    email_from: Optional[str] = None
    payment_gateway_mode: Optional[str] = None
    debug: Optional[bool] = None
    delivery_base_fee: Optional[float] = None
    delivery_per_km_fee: Optional[float] = None
    max_delivery_radius_km: Optional[float] = None
    surge_pricing_enabled: Optional[bool] = None
    surge_multiplier: Optional[float] = None
    platform_fee: Optional[float] = None


@router.get("/settings")
def get_admin_settings(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Retrieve platform runtime configuration."""
    from backend.app.core.config import settings
    from backend.app.services.delivery_pricing_service import DeliveryPricingService
    pricing_policy = DeliveryPricingService.get_pricing_policy(db)
    return {
        "app_name": settings.APP_NAME,
        "app_env": settings.APP_ENV,
        "debug": settings.DEBUG,
        "email_provider": settings.EMAIL_PROVIDER,
        "email_from": settings.EMAIL_FROM,
        "frontend_url": settings.FRONTEND_URL,
        "payment_gateway_mode": settings.PAYMENT_GATEWAY_MODE,
        "cors_origins": settings.cors_origins_list,
        "session_max_age_seconds": settings.SESSION_MAX_AGE_SECONDS,
        **pricing_policy,
    }


@router.put("/settings")
def update_admin_settings(
    payload: AdminSettingsPayload,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update platform configuration."""
    from backend.app.core.config import settings
    from backend.app.services.delivery_pricing_service import DeliveryPricingService

    if payload.app_name is not None:
        settings.APP_NAME = payload.app_name
    if payload.email_provider is not None:
        settings.EMAIL_PROVIDER = payload.email_provider
    if payload.email_from is not None:
        settings.EMAIL_FROM = payload.email_from
    if payload.payment_gateway_mode is not None:
        settings.PAYMENT_GATEWAY_MODE = payload.payment_gateway_mode
    if payload.debug is not None:
        settings.DEBUG = payload.debug

    delivery_keys = {
        "delivery_base_fee",
        "delivery_per_km_fee",
        "max_delivery_radius_km",
        "surge_pricing_enabled",
        "surge_multiplier",
        "platform_fee",
    }
    payload_dict = payload.model_dump(exclude_unset=True)
    delivery_updates = {k: v for k, v in payload_dict.items() if k in delivery_keys}
    if delivery_updates:
        try:
            DeliveryPricingService.update_pricing_policy(db, delivery_updates)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    db.add(AuditLog(
        user_id=admin.id,
        action="PLATFORM_SETTINGS_UPDATED",
        entity_name="PlatformSettings",
        entity_id="global",
        details_json=json.dumps(payload_dict)
    ))
    db.commit()
    return get_admin_settings(admin=admin, db=db)


# ── Admin-Assisted Cancellation for READY Orders ────────────────────────────

from backend.app.models.order import CancellationRequest
from backend.app.models.menu import MenuItem, Ingredient, MenuItemIngredient
from backend.app.models.inventory import InventoryTransaction, Purchase, WasteRecord
from backend.app.models.enums import InventoryTransactionType
from backend.app.schemas.customer import AdminCancellationDecision, CancellationRequestResponse


class _CancellationDecisionRequest(BaseModel):
    decision: Optional[str] = None  # APPROVED | REJECTED (optional when calling /approve or /reject directly)
    admin_note: Optional[str] = Field(None, max_length=500)


@router.get("/cancellation-requests", response_model=List[Dict[str, Any]])
def list_cancellation_requests(
    status_filter: Optional[str] = Query(None, alias="status"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all cancellation requests. Default: PENDING only. Filter by status=APPROVED|REJECTED|ALL."""
    q = db.query(CancellationRequest)
    if status_filter and status_filter.upper() != "ALL":
        q = q.filter(CancellationRequest.status == status_filter.upper())
    elif not status_filter:
        q = q.filter(CancellationRequest.status == "PENDING")
    requests = q.order_by(CancellationRequest.created_at.desc()).all()

    result = []
    for cr in requests:
        order = db.query(Order).filter(Order.id == cr.order_id).first()
        customer = db.query(User).filter(User.id == cr.customer_id).first()
        result.append({
            "id": cr.id,
            "order_id": cr.order_id,
            "order_number": order.order_number if order else None,
            "order_status": order.status.value if order and hasattr(order.status, "value") else str(order.status) if order else None,
            "order_total": order.total_amount if order else None,
            "customer_id": cr.customer_id,
            "customer_name": customer.full_name if customer else None,
            "customer_email": customer.email if customer else None,
            "kitchen_id": cr.kitchen_id,
            "kitchen_name": order.kitchen.kitchen_name if order and order.kitchen else None,
            "reason": cr.reason,
            "customer_note": getattr(cr, "customer_note", None),
            "status": cr.status,
            "admin_id": cr.admin_id,
            "reviewed_by": cr.admin_id,
            "admin_note": cr.admin_note,
            "created_at": cr.created_at.isoformat() if cr.created_at else None,
            "requested_at": cr.created_at.isoformat() if cr.created_at else None,
            "resolved_at": cr.resolved_at.isoformat() if cr.resolved_at else None,
            "reviewed_at": cr.resolved_at.isoformat() if cr.resolved_at else None,
        })
    return result


@router.get("/cancellation-requests/{request_id}", response_model=Dict[str, Any])
def get_cancellation_request_detail(
    request_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get single cancellation request details for admin review."""
    cr = db.query(CancellationRequest).filter(CancellationRequest.id == request_id).first()
    if not cr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cancellation request not found.")
    order = db.query(Order).filter(Order.id == cr.order_id).first()
    customer = db.query(User).filter(User.id == cr.customer_id).first()
    return {
        "id": cr.id,
        "order_id": cr.order_id,
        "order_number": order.order_number if order else None,
        "order_status": order.status.value if order and hasattr(order.status, "value") else str(order.status) if order else None,
        "order_total": order.total_amount if order else None,
        "customer_id": cr.customer_id,
        "customer_name": customer.full_name if customer else None,
        "customer_email": customer.email if customer else None,
        "kitchen_id": cr.kitchen_id,
        "kitchen_name": order.kitchen.kitchen_name if order and order.kitchen else None,
        "reason": cr.reason,
        "customer_note": getattr(cr, "customer_note", None),
        "status": cr.status,
        "admin_id": cr.admin_id,
        "reviewed_by": cr.admin_id,
        "admin_note": cr.admin_note,
        "created_at": cr.created_at.isoformat() if cr.created_at else None,
        "requested_at": cr.created_at.isoformat() if cr.created_at else None,
        "resolved_at": cr.resolved_at.isoformat() if cr.resolved_at else None,
        "reviewed_at": cr.resolved_at.isoformat() if cr.resolved_at else None,
    }


def _process_cancellation_decision(
    db: Session,
    admin: User,
    request_id: str,
    decision: str,
    admin_note: Optional[str] = None
) -> Dict[str, Any]:
    decision = (decision or "").upper()
    if decision not in ("APPROVED", "REJECTED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="decision must be APPROVED or REJECTED."
        )

    if decision == "REJECTED" and not (admin_note and admin_note.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rejection reason is required."
        )

    cr = db.query(CancellationRequest).filter(CancellationRequest.id == request_id).first()
    if not cr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cancellation request not found.")

    if cr.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"This cancellation request has already been {cr.status.lower()}."
        )

    order = db.query(Order).filter(Order.id == cr.order_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated order not found.")

    now = datetime.now(timezone.utc)

    # ── APPROVE ──────────────────────────────────────────────────────────────
    if decision == "APPROVED":
        # Verify order is still READY (guard against concurrent state changes)
        if order.status != OrderStatus.READY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot approve cancellation: order is now in '{order.status.value}' state, not READY."
            )

        try:
            # Create recipe-driven wastage records (food was fully prepared)
            existing_waste = db.query(WasteRecord).filter(WasteRecord.order_id == order.id).first()
            if not existing_waste:
                for order_item in order.items:
                    recipe_links = db.query(MenuItemIngredient).filter(
                        MenuItemIngredient.menu_item_id == order_item.menu_item_id
                    ).all() if order_item.menu_item_id else []

                    # Fallback lookup if menu_item_id wasn't set but item_name matches
                    if not recipe_links:
                        menu_item = db.query(MenuItem).filter(MenuItem.name == order_item.item_name).first()
                        if menu_item:
                            recipe_links = db.query(MenuItemIngredient).filter(
                                MenuItemIngredient.menu_item_id == menu_item.id
                            ).all()

                    if recipe_links:
                        for link in recipe_links:
                            ing = db.query(Ingredient).filter(Ingredient.id == link.ingredient_id).first()
                            if not ing:
                                continue
                            wasted_qty = round(link.quantity_required * order_item.quantity, 3)

                            unit_cost = KitchenService._get_ingredient_unit_cost(db, order.kitchen_id, ing.id)
                            est_cost = round(wasted_qty * unit_cost, 2) if unit_cost is not None else None

                            db.add(WasteRecord(
                                kitchen_id=order.kitchen_id,
                                ingredient_id=ing.id,
                                order_id=order.id,
                                menu_item_id=order_item.menu_item_id,
                                menu_item_name=order_item.item_name,
                                portions_wasted=float(order_item.quantity),
                                quantity=wasted_qty,
                                unit=ing.unit,
                                reason="Customer Cancellation — Admin Approved",
                                recorded_by=f"Admin ({admin.email})",
                                estimated_cost=est_cost,
                                source_event="ORDER_CANCELLATION",
                                created_at=now,
                            ))

                            # Reclassify existing OUTWARD_ORDER as WASTE (avoid double deduction)
                            outward_txn = db.query(InventoryTransaction).filter(
                                InventoryTransaction.reference_order_id == order.id,
                                InventoryTransaction.ingredient_id == ing.id,
                                InventoryTransaction.transaction_type == InventoryTransactionType.OUTWARD_ORDER
                            ).first()

                            if outward_txn:
                                db.add(InventoryTransaction(
                                    kitchen_id=order.kitchen_id,
                                    ingredient_id=ing.id,
                                    transaction_type=InventoryTransactionType.ADJUSTMENT,
                                    quantity=abs(outward_txn.quantity),
                                    balance_after=ing.current_stock + abs(outward_txn.quantity),
                                    reference_order_id=order.id,
                                    reason=f"Reclassified consumption to food wastage (admin-approved cancellation)",
                                ))
                                db.add(InventoryTransaction(
                                    kitchen_id=order.kitchen_id,
                                    ingredient_id=ing.id,
                                    transaction_type=InventoryTransactionType.WASTE,
                                    quantity=-wasted_qty,
                                    balance_after=ing.current_stock,
                                    reference_order_id=order.id,
                                    reason=f"Wastage: Admin-approved cancellation of READY order #{order.order_number}",
                                ))
                            else:
                                ing.current_stock = max(0.0, ing.current_stock - wasted_qty)
                                db.add(InventoryTransaction(
                                    kitchen_id=order.kitchen_id,
                                    ingredient_id=ing.id,
                                    transaction_type=InventoryTransactionType.WASTE,
                                    quantity=-wasted_qty,
                                    balance_after=ing.current_stock,
                                    reference_order_id=order.id,
                                    reason=f"Wastage: Admin-approved cancellation of READY order #{order.order_number}",
                                ))
                    else:
                        db.add(WasteRecord(
                            kitchen_id=order.kitchen_id,
                            ingredient_id=None,
                            order_id=order.id,
                            menu_item_id=order_item.menu_item_id,
                            menu_item_name=order_item.item_name,
                            portions_wasted=float(order_item.quantity),
                            quantity=float(order_item.quantity),
                            unit="portion",
                            reason="Customer Cancellation — Admin Approved",
                            recorded_by=f"Admin ({admin.email})",
                            estimated_cost=round(order_item.unit_price * order_item.quantity, 2),
                            source_event="ORDER_CANCELLATION",
                            created_at=now,
                        ))

            # Transition order to CANCELLED
            order.status = OrderStatus.CANCELLED
            order.cancellation_reason = admin_note or "Customer Cancellation — Admin Approved"
            if order.payment_status == PaymentStatus.SUCCESS:
                order.payment_status = PaymentStatus.REFUNDED
            order.updated_at = now

            # Notify customer
            db.add(Notification(
                user_id=cr.customer_id,
                title="Cancellation Approved",
                message=f"Your cancellation request for Order #{order.order_number} was approved by Admin. The order has been cancelled.",
                event_type="ORDER_CANCELLED",
            ))

            # Notify kitchen owner about wastage
            if order.kitchen and order.kitchen.user_id:
                db.add(Notification(
                    user_id=order.kitchen.user_id,
                    title="Order Cancelled — Food Wastage Recorded",
                    message=(
                        f"Order #{order.order_number} was cancelled (admin-approved) while READY. "
                        f"Food wastage has been recorded automatically. "
                        f"Reason: {cr.reason or 'Not provided'}."
                    ),
                    event_type="ORDER_CANCELLED",
                ))

            cr.status = "APPROVED"
            cr.admin_id = admin.id
            cr.admin_note = admin_note
            cr.resolved_at = now

            db.add(AuditLog(
                user_id=admin.id,
                action="CANCELLATION_REQUEST_APPROVED",
                entity_name="CancellationRequest",
                entity_id=cr.id,
                details_json=json.dumps({"order_id": order.id, "order_number": order.order_number, "admin_note": admin_note})
            ))
            db.commit()
            db.refresh(cr)

            return {
                "message": f"Order #{order.order_number} cancelled. Wastage recorded.",
                "request_id": cr.id,
                "order_id": order.id,
                "order_status": "CANCELLED",
                "decision": "APPROVED",
            }
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to approve cancellation request {request_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process cancellation approval: {str(e)}"
            )

    # ── REJECT ───────────────────────────────────────────────────────────────
    else:
        try:
            cr.status = "REJECTED"
            cr.admin_id = admin.id
            cr.admin_note = admin_note.strip()
            cr.resolved_at = now

            # Notify customer of rejection
            db.add(Notification(
                user_id=cr.customer_id,
                title="Cancellation Request Rejected",
                message=f"Your cancellation request for Order #{order.order_number} was rejected. Reason: {admin_note.strip()}.",
                event_type="CANCELLATION_REJECTED",
            ))

            db.add(AuditLog(
                user_id=admin.id,
                action="CANCELLATION_REQUEST_REJECTED",
                entity_name="CancellationRequest",
                entity_id=cr.id,
                details_json=json.dumps({"order_id": order.id, "order_number": order.order_number, "admin_note": admin_note.strip()})
            ))
            db.commit()
            db.refresh(cr)

            return {
                "message": f"Cancellation request rejected. Order #{order.order_number} remains READY.",
                "request_id": cr.id,
                "order_id": order.id,
                "order_status": order.status.value,
                "decision": "REJECTED",
            }
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to reject cancellation request {request_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process cancellation rejection: {str(e)}"
            )


@router.post("/cancellation-requests/{request_id}/decide")
def decide_cancellation_request(
    request_id: str,
    payload: _CancellationDecisionRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin approves or rejects a cancellation request for a READY order."""
    return _process_cancellation_decision(db, admin, request_id, payload.decision, payload.admin_note)


@router.post("/cancellation-requests/{request_id}/approve")
def approve_cancellation_request(
    request_id: str,
    payload: Optional[_CancellationDecisionRequest] = None,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin approves a cancellation request for a READY order."""
    note = payload.admin_note if payload else None
    return _process_cancellation_decision(db, admin, request_id, "APPROVED", note)


@router.post("/cancellation-requests/{request_id}/reject")
def reject_cancellation_request(
    request_id: str,
    payload: Optional[_CancellationDecisionRequest] = None,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin rejects a cancellation request for a READY order with a required reason."""
    note = payload.admin_note if payload else None
    return _process_cancellation_decision(db, admin, request_id, "REJECTED", note)



# ── Admin FSSAI Food License Oversight ─────────────────────────────────────────
@router.get("/kitchens/{kitchen_id}/license", response_model=KitchenLicenseResponse)
def get_admin_kitchen_license(
    kitchen_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Retrieve full license details, OCR inspection data, and document history for a kitchen."""
    kitchen = db.query(KitchenProfile).filter(KitchenProfile.id == kitchen_id).first()
    if not kitchen:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kitchen not found")
    if not kitchen.license:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kitchen has no registered license")
    from backend.app.services.fssai_service import FssaiService
    from backend.app.models.enums import LicenseStatus
    FssaiService.sync_license_expiration(db, kitchen.license)
    is_exp = kitchen.license.status == LicenseStatus.EXPIRED or (kitchen.license.expiry_date and kitchen.license.expiry_date < _utc_now())
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
            ) for doc in kitchen.license.documents
        ]
    )


@router.get("/kitchens/{kitchen_id}/license-document/{doc_id}")
def stream_admin_license_document(
    kitchen_id: str,
    doc_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Secure authenticated viewing of license document for platform administrators."""
    kitchen = db.query(KitchenProfile).filter(KitchenProfile.id == kitchen_id).first()
    if not kitchen:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kitchen not found")
    doc = db.query(KitchenLicenseDocument).filter(KitchenLicenseDocument.id == doc_id).first()
    if not doc or not kitchen.license or doc.license_id != kitchen.license.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found for this kitchen")
    import os
    if not os.path.exists(doc.file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document file missing on disk")
    return FileResponse(path=doc.file_path, media_type=doc.mime_type, filename=doc.original_filename)


@router.post("/kitchens/{kitchen_id}/license/verify")
def verify_kitchen_license(
    kitchen_id: str,
    req: LicenseVerificationRequest = LicenseVerificationRequest(),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Officially mark kitchen license as VERIFIED with source recording and audit trail."""
    kitchen = db.query(KitchenProfile).filter(KitchenProfile.id == kitchen_id).first()
    if not kitchen or not kitchen.license:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kitchen license not found")

    from backend.app.services.fssai_service import is_test_identifier
    from backend.app.models.enums import LicenseStatus
    if is_test_identifier(kitchen.license.license_number) and req.verification_source != "DEMO_TEST":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Test/Demo identifiers cannot be officially verified. Use authentic verification source or demo test mode."
        )

    # Enforce duplicate protection: cannot verify if another kitchen already holds this verified license
    duplicate_verified = db.query(KitchenLicense).filter(
        KitchenLicense.license_number == kitchen.license.license_number,
        KitchenLicense.kitchen_id != kitchen.id,
        KitchenLicense.status == LicenseStatus.VERIFIED,
    ).first()
    if duplicate_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot verify license: duplicate license number is already verified for another kitchen.",
        )

    kitchen.license.status = LicenseStatus.VERIFIED
    kitchen.license.verification_source = req.verification_source or "MANUAL_ADMIN"
    kitchen.license.verified_by_user_id = admin.id
    kitchen.license.verified_at = _utc_now()
    kitchen.license.correction_reason = None
    kitchen.license.rejection_reason = None
    kitchen.license.updated_at = _utc_now()

    # If kitchen was blocked due to correction required, allow it to become approved
    kitchen.approval_status = "APPROVED"
    kitchen.is_approved = True
    kitchen.updated_at = _utc_now()

    db.add(Notification(
        user_id=kitchen.user_id,
        title="FSSAI License Verified!",
        message=f"Your FSSAI Food License ({kitchen.license.license_number}) for '{kitchen.kitchen_name}' has been verified by platform administration.",
        event_type="NOTIFICATION_CREATED"
    ))
    db.add(AuditLog(
        user_id=admin.id,
        action="LICENSE_VERIFIED",
        entity_name="KitchenLicense",
        entity_id=kitchen.license.id,
        details_json=json.dumps({"kitchen_name": kitchen.kitchen_name, "license_number": kitchen.license.license_number, "source": req.verification_source, "verified_by": admin.email})
    ))
    db.commit()

    try:
        from backend.app.websockets.connection_manager import ws_manager
        lic_payload = {
            "kitchen_id": kitchen.id,
            "kitchen_name": kitchen.kitchen_name,
            "license_status": "VERIFIED",
            "approval_status": "APPROVED",
            "is_approved": True,
            "updated_at": kitchen.updated_at.isoformat() if kitchen.updated_at else None,
        }
        ws_manager.publish_event(
            event_type="LICENSE_STATUS_UPDATED",
            data=lic_payload,
            target_user_id=kitchen.user_id,
        )
        ws_manager.publish_event(
            event_type="LICENSE_STATUS_UPDATED",
            data=lic_payload,
            target_kitchen_id=kitchen.id,
        )
        ws_manager.publish_event(
            event_type="LICENSE_STATUS_UPDATED",
            data=lic_payload,
            target_role="ADMIN",
        )
    except Exception as ws_err:
        logger.warning(f"Error publishing license verification event: {ws_err}")

    return {"success": True, "message": "License verified successfully", "status": "VERIFIED"}


@router.post("/kitchens/{kitchen_id}/license/request-correction")
def request_license_correction(
    kitchen_id: str,
    req: LicenseCorrectionRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Request corrections on kitchen license with specific feedback for the owner."""
    kitchen = db.query(KitchenProfile).filter(KitchenProfile.id == kitchen_id).first()
    if not kitchen or not kitchen.license:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kitchen license not found")

    reason_text = req.correction_reason or req.reason or "Correction required by administration."
    from backend.app.models.enums import LicenseStatus
    kitchen.license.status = LicenseStatus.CORRECTION_REQUIRED
    kitchen.license.correction_reason = reason_text
    kitchen.license.updated_at = _utc_now()
    kitchen.approval_status = "CORRECTION_REQUIRED"
    kitchen.is_approved = False
    kitchen.is_open = False
    kitchen.updated_at = _utc_now()

    db.add(Notification(
        user_id=kitchen.user_id,
        title="Action Required: License Correction",
        message=f"Your FSSAI License for '{kitchen.kitchen_name}' requires corrections: {reason_text}. Please update your document or details.",
        event_type="NOTIFICATION_CREATED"
    ))
    db.add(AuditLog(
        user_id=admin.id,
        action="LICENSE_CORRECTION_REQUESTED",
        entity_name="KitchenLicense",
        entity_id=kitchen.license.id,
        details_json=json.dumps({"kitchen_name": kitchen.kitchen_name, "reason": reason_text, "requested_by": admin.email})
    ))
    db.commit()

    try:
        from backend.app.websockets.connection_manager import ws_manager
        lic_payload = {
            "kitchen_id": kitchen.id,
            "kitchen_name": kitchen.kitchen_name,
            "license_status": "CORRECTION_REQUIRED",
            "approval_status": "CORRECTION_REQUIRED",
            "is_approved": False,
            "correction_reason": reason_text,
            "updated_at": kitchen.updated_at.isoformat() if kitchen.updated_at else None,
        }
        ws_manager.publish_event(
            event_type="LICENSE_STATUS_UPDATED",
            data=lic_payload,
            target_user_id=kitchen.user_id,
        )
        ws_manager.publish_event(
            event_type="LICENSE_STATUS_UPDATED",
            data=lic_payload,
            target_kitchen_id=kitchen.id,
        )
        ws_manager.publish_event(
            event_type="LICENSE_STATUS_UPDATED",
            data=lic_payload,
            target_role="ADMIN",
        )
    except Exception as ws_err:
        logger.warning(f"Error publishing license correction event: {ws_err}")

    return {"success": True, "message": "Correction requested successfully", "status": "CORRECTION_REQUIRED"}


@router.post("/kitchens/{kitchen_id}/license/reject")
def reject_kitchen_license(
    kitchen_id: str,
    req: LicenseRejectionRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Reject kitchen license application with documented reason."""
    kitchen = db.query(KitchenProfile).filter(KitchenProfile.id == kitchen_id).first()
    if not kitchen or not kitchen.license:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kitchen license not found")

    reason_text = req.rejection_reason or req.reason or "License application rejected by administration."
    from backend.app.models.enums import LicenseStatus
    kitchen.license.status = LicenseStatus.REJECTED
    kitchen.license.rejection_reason = reason_text
    kitchen.license.updated_at = _utc_now()
    kitchen.approval_status = "REJECTED"
    kitchen.is_approved = False
    kitchen.is_open = False
    kitchen.updated_at = _utc_now()

    db.add(Notification(
        user_id=kitchen.user_id,
        title="License Application Rejected",
        message=f"Your FSSAI License for '{kitchen.kitchen_name}' was rejected: {reason_text}.",
        event_type="NOTIFICATION_CREATED"
    ))
    db.add(AuditLog(
        user_id=admin.id,
        action="LICENSE_REJECTED",
        entity_name="KitchenLicense",
        entity_id=kitchen.license.id,
        details_json=json.dumps({"kitchen_name": kitchen.kitchen_name, "reason": reason_text, "rejected_by": admin.email})
    ))
    db.commit()

    try:
        from backend.app.websockets.connection_manager import ws_manager
        lic_payload = {
            "kitchen_id": kitchen.id,
            "kitchen_name": kitchen.kitchen_name,
            "license_status": "REJECTED",
            "approval_status": "REJECTED",
            "is_approved": False,
            "rejection_reason": reason_text,
            "updated_at": kitchen.updated_at.isoformat() if kitchen.updated_at else None,
        }
        ws_manager.publish_event(
            event_type="LICENSE_STATUS_UPDATED",
            data=lic_payload,
            target_user_id=kitchen.user_id,
        )
        ws_manager.publish_event(
            event_type="LICENSE_STATUS_UPDATED",
            data=lic_payload,
            target_kitchen_id=kitchen.id,
        )
        ws_manager.publish_event(
            event_type="LICENSE_STATUS_UPDATED",
            data=lic_payload,
            target_role="ADMIN",
        )
    except Exception as ws_err:
        logger.warning(f"Error publishing license rejection event: {ws_err}")

    return {"success": True, "message": "License rejected", "status": "REJECTED"}
