"""Admin API routes - Platform administration endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import Optional
from uuid import UUID
from datetime import datetime

from app.database.session import get_db
from app.api.deps import require_admin
from app.models.user import (
    User, UserRole, UserStatus, CustomerProfile, KitchenProfile,
    MenuItem, Order, OrderStatus, Payment, PaymentStatus,
    Inventory, Ingredient, Review, Promotion, WasteRecord,
    DemandPrediction, AuditLog
)
from app.schemas.admin import (
    DashboardStats, UserListResponse, UserDetailResponse,
    KitchenListResponse, OrderListResponse, PaymentListResponse,
    InventoryListResponse, ReviewListResponse, PromotionListResponse,
    WasteListResponse, DemandPredictionListResponse, AuditLogListResponse,
    AnalyticsResponse, UserStatusUpdate
)

router = APIRouter(prefix="/admin", tags=["Admin"])


# =============================================
# DASHBOARD
# =============================================

@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get dashboard statistics - ADMIN only."""
    
    # User counts
    total_users = await db.execute(select(func.count(User.id)))
    total_users_count = total_users.scalar() or 0
    
    customers = await db.execute(
        select(func.count(User.id)).where(User.role == UserRole.CUSTOMER)
    )
    customers_count = customers.scalar() or 0
    
    kitchen_owners = await db.execute(
        select(func.count(User.id)).where(User.role == UserRole.KITCHEN_OWNER)
    )
    kitchen_owners_count = kitchen_owners.scalar() or 0
    
    # Kitchen count
    kitchens = await db.execute(select(func.count(KitchenProfile.id)))
    kitchens_count = kitchens.scalar() or 0
    
    # Order counts
    total_orders = await db.execute(select(func.count(Order.id)))
    total_orders_count = total_orders.scalar() or 0
    
    pending_orders = await db.execute(
        select(func.count(Order.id)).where(Order.status == OrderStatus.PENDING)
    )
    pending_orders_count = pending_orders.scalar() or 0
    
    completed_orders = await db.execute(
        select(func.count(Order.id)).where(Order.status == OrderStatus.DELIVERED)
    )
    completed_orders_count = completed_orders.scalar() or 0
    
    cancelled_orders = await db.execute(
        select(func.count(Order.id)).where(Order.status == OrderStatus.CANCELLED)
    )
    cancelled_orders_count = cancelled_orders.scalar() or 0
    
    # Revenue
    revenue = await db.execute(
        select(func.sum(Order.total_amount)).where(
            Order.status.in_([OrderStatus.DELIVERED, OrderStatus.CONFIRMED])
        )
    )
    revenue_total = revenue.scalar() or 0.0
    
    # Low stock items
    low_stock = await db.execute(
        select(func.count(Inventory.id)).where(
            Inventory.quantity_on_hand <= Inventory.min_quantity
        )
    )
    low_stock_count = low_stock.scalar() or 0
    
    # Reviews
    reviews = await db.execute(select(func.count(Review.id)))
    reviews_count = reviews.scalar() or 0
    
    # Waste records
    waste = await db.execute(select(func.count(WasteRecord.id)))
    waste_count = waste.scalar() or 0
    
    return DashboardStats(
        total_users=total_users_count,
        customers=customers_count,
        kitchen_owners=kitchen_owners_count,
        kitchens=kitchens_count,
        total_orders=total_orders_count,
        pending_orders=pending_orders_count,
        completed_orders=completed_orders_count,
        cancelled_orders=cancelled_orders_count,
        revenue=revenue_total,
        low_stock_items=low_stock_count,
        reviews=reviews_count,
        waste_records=waste_count
    )


# =============================================
# USER MANAGEMENT
# =============================================

@router.get("/users", response_model=UserListResponse)
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = None,
    role: Optional[str] = None,
    status_filter: Optional[str] = None,
    verified: Optional[bool] = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """List users with filters - ADMIN only."""
    query = select(User)
    
    # Apply filters
    if search:
        query = query.where(
            User.email.ilike(f"%{search}%") |
            User.first_name.ilike(f"%{search}%") |
            User.last_name.ilike(f"%{search}%")
        )
    
    if role:
        query = query.where(User.role == UserRole(role))
    
    if status_filter:
        query = query.where(User.status == UserStatus(status_filter))
    
    if verified is not None:
        query = query.where(User.is_email_verified == verified)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.execute(count_query)
    total_count = total.scalar() or 0
    
    # Apply pagination
    query = query.offset(skip).limit(limit).order_by(User.created_at.desc())
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    return UserListResponse(
        users=users,
        total=total_count,
        skip=skip,
        limit=limit
    )


@router.get("/users/{user_id}", response_model=UserDetailResponse)
async def get_user_detail(
    user_id: UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get user details - ADMIN only."""
    result = await db.execute(
        select(User)
        .options(
            selectinload(User.customer_profile),
            selectinload(User.kitchen_profile)
        )
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user


@router.patch("/users/{user_id}/status")
async def update_user_status(
    user_id: UUID,
    status_update: UserStatusUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update user status - ADMIN only."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot modify your own status")
    
    user.status = UserStatus(status_update.status)
    await db.commit()
    
    return {"message": "User status updated successfully"}


# =============================================
# KITCHEN MANAGEMENT
# =============================================

@router.get("/kitchens", response_model=KitchenListResponse)
async def list_kitchens(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """List kitchens - ADMIN only."""
    query = select(KitchenProfile).options(selectinload(KitchenProfile.user))
    
    if search:
        query = query.where(KitchenProfile.kitchen_name.ilike(f"%{search}%"))
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.execute(count_query)
    total_count = total.scalar() or 0
    
    # Apply pagination
    query = query.offset(skip).limit(limit).order_by(KitchenProfile.created_at.desc())
    
    result = await db.execute(query)
    kitchens = result.scalars().all()
    
    return KitchenListResponse(
        kitchens=kitchens,
        total=total_count,
        skip=skip,
        limit=limit
    )


@router.get("/kitchen-owners", response_model=KitchenListResponse)
async def list_kitchen_owners(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """List kitchen owners - ADMIN only."""
    query = (
        select(User)
        .where(User.role == UserRole.KITCHEN_OWNER)
        .options(selectinload(User.kitchen_profile))
    )
    
    if search:
        query = query.where(
            User.email.ilike(f"%{search}%") |
            User.first_name.ilike(f"%{search}%") |
            User.last_name.ilike(f"%{search}%")
        )
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.execute(count_query)
    total_count = total.scalar() or 0
    
    # Apply pagination
    query = query.offset(skip).limit(limit).order_by(User.created_at.desc())
    
    result = await db.execute(query)
    owners = result.scalars().all()
    
    return KitchenListResponse(
        kitchens=owners,
        total=total_count,
        skip=skip,
        limit=limit
    )


# =============================================
# MENU MANAGEMENT
# =============================================

@router.get("/menu")
async def list_menu_items(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = None,
    kitchen_id: Optional[UUID] = None,
    available: Optional[bool] = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """List menu items - ADMIN only."""
    query = select(MenuItem).options(selectinload(MenuItem.kitchen))
    
    if search:
        query = query.where(MenuItem.name.ilike(f"%{search}%"))
    
    if kitchen_id:
        query = query.where(MenuItem.kitchen_id == kitchen_id)
    
    if available is not None:
        query = query.where(MenuItem.is_available == available)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.execute(count_query)
    total_count = total.scalar() or 0
    
    # Apply pagination
    query = query.offset(skip).limit(limit).order_by(MenuItem.created_at.desc())
    
    result = await db.execute(query)
    items = result.scalars().all()
    
    return {
        "items": items,
        "total": total_count,
        "skip": skip,
        "limit": limit
    }


# =============================================
# ORDER MANAGEMENT
# =============================================

@router.get("/orders", response_model=OrderListResponse)
async def list_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status_filter: Optional[str] = None,
    customer_id: Optional[UUID] = None,
    kitchen_id: Optional[UUID] = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """List orders - ADMIN only."""
    query = select(Order).options(
        selectinload(Order.customer),
        selectinload(Order.kitchen),
        selectinload(Order.payment)
    )
    
    if status_filter:
        query = query.where(Order.status == OrderStatus(status_filter))
    
    if customer_id:
        query = query.where(Order.customer_id == customer_id)
    
    if kitchen_id:
        query = query.where(Order.kitchen_id == kitchen_id)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.execute(count_query)
    total_count = total.scalar() or 0
    
    # Apply pagination
    query = query.offset(skip).limit(limit).order_by(Order.created_at.desc())
    
    result = await db.execute(query)
    orders = result.scalars().all()
    
    return OrderListResponse(
        orders=orders,
        total=total_count,
        skip=skip,
        limit=limit
    )


# =============================================
# PAYMENT MANAGEMENT
# =============================================

@router.get("/payments", response_model=PaymentListResponse)
async def list_payments(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status_filter: Optional[str] = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """List payments - ADMIN only."""
    query = select(Payment).options(
        selectinload(Payment.order).selectinload(Order.customer)
    )
    
    if status_filter:
        query = query.where(Payment.status == PaymentStatus(status_filter))
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.execute(count_query)
    total_count = total.scalar() or 0
    
    # Apply pagination
    query = query.offset(skip).limit(limit).order_by(Payment.created_at.desc())
    
    result = await db.execute(query)
    payments = result.scalars().all()
    
    return PaymentListResponse(
        payments=payments,
        total=total_count,
        skip=skip,
        limit=limit
    )


# =============================================
# INVENTORY MANAGEMENT
# =============================================

@router.get("/inventory", response_model=InventoryListResponse)
async def list_inventory(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    kitchen_id: Optional[UUID] = None,
    low_stock: Optional[bool] = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """List inventory - ADMIN only."""
    query = select(Inventory).options(
        selectinload(Inventory.kitchen),
        selectinload(Inventory.ingredient)
    )
    
    if kitchen_id:
        query = query.where(Inventory.kitchen_id == kitchen_id)
    
    if low_stock is not None:
        if low_stock:
            query = query.where(Inventory.quantity_on_hand <= Inventory.min_quantity)
        else:
            query = query.where(Inventory.quantity_on_hand > Inventory.min_quantity)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.execute(count_query)
    total_count = total.scalar() or 0
    
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    inventory = result.scalars().all()
    
    return InventoryListResponse(
        inventory=inventory,
        total=total_count,
        skip=skip,
        limit=limit
    )


# =============================================
# REVIEWS
# =============================================

@router.get("/reviews", response_model=ReviewListResponse)
async def list_reviews(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    kitchen_id: Optional[UUID] = None,
    min_rating: Optional[int] = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """List reviews - ADMIN only."""
    query = select(Review).options(
        selectinload(Review.user),
        selectinload(Review.kitchen)
    )
    
    if kitchen_id:
        query = query.where(Review.kitchen_id == kitchen_id)
    
    if min_rating:
        query = query.where(Review.rating >= min_rating)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.execute(count_query)
    total_count = total.scalar() or 0
    
    # Apply pagination
    query = query.offset(skip).limit(limit).order_by(Review.created_at.desc())
    
    result = await db.execute(query)
    reviews = result.scalars().all()
    
    return ReviewListResponse(
        reviews=reviews,
        total=total_count,
        skip=skip,
        limit=limit
    )


# =============================================
# PROMOTIONS
# =============================================

@router.get("/promotions", response_model=PromotionListResponse)
async def list_promotions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    active: Optional[bool] = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """List promotions - ADMIN only."""
    query = select(Promotion).options(selectinload(Promotion.kitchen))
    
    if active is not None:
        query = query.where(Promotion.is_active == active)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.execute(count_query)
    total_count = total.scalar() or 0
    
    # Apply pagination
    query = query.offset(skip).limit(limit).order_by(Promotion.created_at.desc())
    
    result = await db.execute(query)
    promotions = result.scalars().all()
    
    return PromotionListResponse(
        promotions=promotions,
        total=total_count,
        skip=skip,
        limit=limit
    )


# =============================================
# WASTE MANAGEMENT
# =============================================

@router.get("/waste", response_model=WasteListResponse)
async def list_waste_records(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    kitchen_id: Optional[UUID] = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """List waste records - ADMIN only."""
    query = select(WasteRecord).options(
        selectinload(WasteRecord.kitchen),
        selectinload(WasteRecord.ingredient)
    )
    
    if kitchen_id:
        query = query.where(WasteRecord.kitchen_id == kitchen_id)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.execute(count_query)
    total_count = total.scalar() or 0
    
    # Apply pagination
    query = query.offset(skip).limit(limit).order_by(WasteRecord.recorded_at.desc())
    
    result = await db.execute(query)
    waste_records = result.scalars().all()
    
    return WasteListResponse(
        waste_records=waste_records,
        total=total_count,
        skip=skip,
        limit=limit
    )


# =============================================
# DEMAND PREDICTIONS
# =============================================

@router.get("/demand-predictions", response_model=DemandPredictionListResponse)
async def list_demand_predictions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    kitchen_id: Optional[UUID] = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """List demand predictions - ADMIN only."""
    query = select(DemandPrediction).options(
        selectinload(DemandPrediction.kitchen),
        selectinload(DemandPrediction.menu_item)
    )
    
    if kitchen_id:
        query = query.where(DemandPrediction.kitchen_id == kitchen_id)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.execute(count_query)
    total_count = total.scalar() or 0
    
    # Apply pagination
    query = query.offset(skip).limit(limit).order_by(DemandPrediction.prediction_date.desc())
    
    result = await db.execute(query)
    predictions = result.scalars().all()
    
    return DemandPredictionListResponse(
        predictions=predictions,
        total=total_count,
        skip=skip,
        limit=limit
    )


# =============================================
# ANALYTICS
# =============================================

@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get analytics data - ADMIN only."""
    
    # Orders over time (last 30 days)
    orders_query = (
        select(
            func.date_trunc('day', Order.created_at).label('date'),
            func.count(Order.id).label('count')
        )
        .where(Order.created_at >= func.now() - func.cast('30 days', type_=func.cast))
        .group_by(func.date_trunc('day', Order.created_at))
        .order_by(func.date_trunc('day', Order.created_at))
    )
    orders_result = await db.execute(orders_query)
    orders_over_time = [{"date": str(row.date), "count": row.count} for row in orders_result]
    
    # Revenue over time
    revenue_query = (
        select(
            func.date_trunc('day', Order.created_at).label('date'),
            func.sum(Order.total_amount).label('revenue')
        )
        .where(
            Order.status.in_([OrderStatus.DELIVERED, OrderStatus.CONFIRMED]),
            Order.created_at >= func.now() - func.cast('30 days', type_=func.cast)
        )
        .group_by(func.date_trunc('day', Order.created_at))
        .order_by(func.date_trunc('day', Order.created_at))
    )
    revenue_result = await db.execute(revenue_query)
    revenue_over_time = [{"date": str(row.date), "revenue": float(row.revenue or 0)} for row in revenue_result]
    
    # Order status distribution
    status_query = (
        select(Order.status, func.count(Order.id))
        .group_by(Order.status)
    )
    status_result = await db.execute(status_query)
    order_status = [{"status": row[0].value, "count": row[1]} for row in status_result]
    
    # Kitchen activity
    kitchen_query = (
        select(
            KitchenProfile.kitchen_name,
            func.count(Order.id).label('order_count')
        )
        .join(Order, Order.kitchen_id == KitchenProfile.id)
        .group_by(KitchenProfile.id, KitchenProfile.kitchen_name)
        .order_by(func.count(Order.id).desc())
        .limit(10)
    )
    kitchen_result = await db.execute(kitchen_query)
    kitchen_activity = [{"kitchen": row.kitchen_name, "orders": row.order_count} for row in kitchen_result]
    
    # Popular menu items
    menu_query = (
        select(
            MenuItem.name,
            func.sum(OrderItem.quantity).label('total_ordered')
        )
        .join(OrderItem, OrderItem.menu_item_id == MenuItem.id)
        .group_by(MenuItem.id, MenuItem.name)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(10)
    )
    menu_result = await db.execute(menu_query)
    popular_items = [{"item": row.name, "ordered": int(row.total_ordered or 0)} for row in menu_result]
    
    # Customer growth
    customer_query = (
        select(
            func.date_trunc('day', User.created_at).label('date'),
            func.count(User.id).label('count')
        )
        .where(
            User.role == UserRole.CUSTOMER,
            User.created_at >= func.now() - func.cast('30 days', type_=func.cast)
        )
        .group_by(func.date_trunc('day', User.created_at))
        .order_by(func.date_trunc('day', User.created_at))
    )
    customer_result = await db.execute(customer_query)
    customer_growth = [{"date": str(row.date), "count": row.count} for row in customer_result]
    
    # Inventory status
    inventory_query = (
        select(
            func.count(Inventory.id).label('total'),
            func.count(Inventory.id).filter(
                Inventory.quantity_on_hand <= Inventory.min_quantity
            ).label('low_stock')
        )
    )
    inventory_result = await db.execute(inventory_query)
    inv_row = inventory_result.one()
    inventory_status = {
        "total": inv_row.total or 0,
        "low_stock": inv_row.low_stock or 0
    }
    
    # Waste trends
    waste_query = (
        select(
            func.date_trunc('day', WasteRecord.recorded_at).label('date'),
            func.sum(WasteRecord.cost).label('cost')
        )
        .where(WasteRecord.recorded_at >= func.now() - func.cast('30 days', type_=func.cast))
        .group_by(func.date_trunc('day', WasteRecord.recorded_at))
        .order_by(func.date_trunc('day', WasteRecord.recorded_at))
    )
    waste_result = await db.execute(waste_query)
    waste_trends = [{"date": str(row.date), "cost": float(row.cost or 0)} for row in waste_result]
    
    return AnalyticsResponse(
        orders_over_time=orders_over_time,
        revenue_over_time=revenue_over_time,
        order_status=order_status,
        kitchen_activity=kitchen_activity,
        popular_items=popular_items,
        customer_growth=customer_growth,
        inventory_status=inventory_status,
        waste_trends=waste_trends
    )


# =============================================
# AUDIT LOGS
# =============================================

@router.get("/audit-logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user_id: Optional[UUID] = None,
    action: Optional[str] = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """List audit logs - ADMIN only."""
    query = select(AuditLog).options(selectinload(AuditLog.user))
    
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    
    if action:
        query = query.where(AuditLog.action == action)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.execute(count_query)
    total_count = total.scalar() or 0
    
    # Apply pagination
    query = query.offset(skip).limit(limit).order_by(AuditLog.created_at.desc())
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return AuditLogListResponse(
        logs=logs,
        total=total_count,
        skip=skip,
        limit=limit
    )
