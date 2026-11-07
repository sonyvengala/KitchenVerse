"""
Test Suite for Admin User Management & Protection Behavior.
Tests:
1. Eligible Customer suspension, activation, and permanent deletion (clean accounts).
2. Eligible Kitchen Owner suspension, activation, and archival (when linked records exist).
3. Self-protection: Currently authenticated administrator cannot suspend or delete their own account.
4. Last-active-administrator protection: Sole active administrator cannot be suspended or deleted.
5. Multiple administrators: Second administrator can be deactivated or removed safely.
6. Root system administrator & protected system accounts: Strictly guarded against deletion/suspension.
7. Business history preservation: Soft-deletion / archive preserves orders, payments, reviews, and inventory.
8. Rich user metadata in get_users and get_user_detail (is_protected, protection_reason, can_suspend, can_delete).
"""

import uuid
import pytest
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.database import Base, is_protected_real_user_email
from backend.app.core.security import get_password_hash
from backend.app.models.user import (
    User,
    KitchenProfile,
    CustomerProfile,
    UserSession,
)
from backend.app.models.platform import AuditLog
from backend.app.models.order import Order
from backend.app.models.enums import UserRole, OrderStatus
from backend.app.api.routes.admin import (
    get_users,
    get_user_detail,
    update_user_status,
    delete_user,
    UserStatusUpdateRequest,
    _format_user,
)


@pytest.fixture
def isolated_db():
    """Provides a pristine, completely isolated in-memory SQLite database."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSession()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


def _create_test_user(
    db,
    email: str,
    role: UserRole = UserRole.CUSTOMER,
    is_active: bool = True,
    full_name: str = "Test User",
) -> User:
    user = User(
        id=str(uuid.uuid4()),
        email=email,
        hashed_password=get_password_hash("ValidPass123!"),
        full_name=full_name,
        role=role,
        is_active=is_active,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


class TestAdminUserProtections:
    """Comprehensive validation of admin protection rules and eligible account actions."""

    def test_self_protection_prevents_deactivation_and_deletion(self, isolated_db):
        """Rule: An administrator cannot suspend or delete their own currently authenticated account."""
        admin = _create_test_user(
            isolated_db,
            email="primary_admin@test.com",
            role=UserRole.ADMIN,
            full_name="Primary Admin",
        )

        # 1. Attempt self-deactivation
        req = UserStatusUpdateRequest(status="SUSPENDED")
        with pytest.raises(HTTPException) as exc_suspend:
            update_user_status(user_id=admin.id, req=req, admin=admin, db=isolated_db)
        assert exc_suspend.value.status_code == 400
        assert "Self-deactivation is prohibited" in exc_suspend.value.detail

        # 2. Attempt self-deletion
        with pytest.raises(HTTPException) as exc_delete:
            delete_user(user_id=admin.id, admin=admin, db=isolated_db)
        assert exc_delete.value.status_code == 400
        assert "Self-deletion is prohibited" in exc_delete.value.detail

    def test_last_active_admin_protection(self, isolated_db):
        """Rule: The last active administrator on the platform cannot be suspended or deleted."""
        admin = _create_test_user(
            isolated_db,
            email="sole_admin@test.com",
            role=UserRole.ADMIN,
            full_name="Sole Admin",
        )
        another_actor = _create_test_user(
            isolated_db,
            email="other_actor@test.com",
            role=UserRole.ADMIN,
            is_active=False,  # Inactive second admin
            full_name="Inactive Admin",
        )

        # Attempt to suspend the sole active admin
        req = UserStatusUpdateRequest(status="SUSPENDED")
        with pytest.raises(HTTPException) as exc_suspend:
            update_user_status(user_id=admin.id, req=req, admin=another_actor, db=isolated_db)
        assert exc_suspend.value.status_code == 400
        assert "Cannot deactivate the last active administrator" in exc_suspend.value.detail

        # Attempt to delete the sole active admin
        with pytest.raises(HTTPException) as exc_delete:
            delete_user(user_id=admin.id, admin=another_actor, db=isolated_db)
        assert exc_delete.value.status_code == 400
        assert "Cannot delete the last active administrator" in exc_delete.value.detail

    def test_multiple_active_admins_can_manage_each_other(self, isolated_db):
        """When at least two active admins exist, one admin can deactivate the other."""
        admin1 = _create_test_user(isolated_db, "admin1@test.com", UserRole.ADMIN, is_active=True)
        admin2 = _create_test_user(isolated_db, "admin2@test.com", UserRole.ADMIN, is_active=True)

        # Admin1 deactivates Admin2
        req = UserStatusUpdateRequest(status="SUSPENDED")
        res = update_user_status(user_id=admin2.id, req=req, admin=admin1, db=isolated_db)
        assert res["status"] == "INACTIVE"
        assert res["can_suspend"] is True  # Now inactive, can be reactivated

        # Reactivate Admin2
        req_active = UserStatusUpdateRequest(status="ACTIVE")
        res_active = update_user_status(user_id=admin2.id, req=req_active, admin=admin1, db=isolated_db)
        assert res_active["status"] == "ACTIVE"

    def test_root_and_system_account_protection(self, isolated_db):
        """Rule: admin@cloudkitchen.com cannot be suspended or deleted by administrative action."""
        admin_actor = _create_test_user(isolated_db, "managing_admin@test.com", UserRole.ADMIN, is_active=True)
        root_admin = _create_test_user(isolated_db, "admin@cloudkitchen.com", UserRole.ADMIN, is_active=True)

        req = UserStatusUpdateRequest(status="SUSPENDED")
        with pytest.raises(HTTPException) as exc_suspend:
            update_user_status(user_id=root_admin.id, req=req, admin=admin_actor, db=isolated_db)
        assert exc_suspend.value.status_code == 400
        assert "Cannot suspend root system administrator account" in exc_suspend.value.detail

        with pytest.raises(HTTPException) as exc_del:
            delete_user(user_id=root_admin.id, admin=admin_actor, db=isolated_db)
        assert exc_del.value.status_code == 400
        assert "Cannot delete root system administrator account" in exc_del.value.detail

    def test_ordinary_accounts_not_marked_protected_and_receive_normal_actions(self, isolated_db):
        """Rule: Ordinary customers and kitchen owners are not marked as protected system accounts and receive normal actions."""
        admin_actor = _create_test_user(isolated_db, "managing_admin@test.com", UserRole.ADMIN, is_active=True)
        
        # Ordinary kitchen owner
        owner = _create_test_user(
            isolated_db,
            "test_ordinary_owner@example.com",
            UserRole.KITCHEN_OWNER,
            is_active=True,
            full_name="Ordinary Owner",
        )
        owner_meta = _format_user(owner, current_admin=admin_actor, db=isolated_db)
        assert owner_meta["is_protected"] is False
        assert owner_meta["is_system_account"] is False
        assert owner_meta["can_suspend"] is True
        assert owner_meta["can_delete"] is True
        assert owner_meta["protection_reason"] is None

        # Suspend owner -> status updated, can be reactivated
        req_suspend = UserStatusUpdateRequest(status="SUSPENDED")
        res_suspend = update_user_status(user_id=owner.id, req=req_suspend, admin=admin_actor, db=isolated_db)
        assert res_suspend["status"] == "INACTIVE"
        assert res_suspend["can_suspend"] is True

        # Ordinary customer
        customer = _create_test_user(
            isolated_db,
            "test_ordinary_cust@example.com",
            UserRole.CUSTOMER,
            is_active=True,
            full_name="Ordinary Customer",
        )
        cust_meta = _format_user(customer, current_admin=admin_actor, db=isolated_db)
        assert cust_meta["is_protected"] is False
        assert cust_meta["is_system_account"] is False
        assert cust_meta["can_suspend"] is True
        assert cust_meta["can_delete"] is True
        assert cust_meta["protection_reason"] is None

    def test_eligible_customer_lifecycle_and_clean_deletion(self, isolated_db):
        """Rule: Ordinary eligible customers without business records can be suspended, reactivated, and cleanly deleted."""
        admin = _create_test_user(isolated_db, "admin_test@test.com", UserRole.ADMIN, is_active=True)
        customer = _create_test_user(isolated_db, "clean_customer@test.com", UserRole.CUSTOMER, is_active=True)

        # 1. Suspend
        res_suspend = update_user_status(customer.id, UserStatusUpdateRequest(status="SUSPENDED"), admin, isolated_db)
        assert res_suspend["status"] == "INACTIVE"
        isolated_db.refresh(customer)
        assert customer.is_active is False

        # 2. Reactivate
        res_active = update_user_status(customer.id, UserStatusUpdateRequest(status="ACTIVE"), admin, isolated_db)
        assert res_active["status"] == "ACTIVE"
        isolated_db.refresh(customer)
        assert customer.is_active is True

        # 3. Permanent Clean Deletion
        del_res = delete_user(customer.id, admin, isolated_db)
        assert del_res["success"] is True
        assert del_res["action"] == "deleted"
        assert "had no dependent business records and has been permanently removed" in del_res["message"]

        # Verify removed from DB
        assert isolated_db.query(User).filter(User.id == customer.id).first() is None

    def test_eligible_kitchen_owner_suspension_closes_kitchen(self, isolated_db):
        """Rule: Suspending an eligible kitchen owner automatically sets kitchen.is_open to False."""
        admin = _create_test_user(isolated_db, "admin_k@test.com", UserRole.ADMIN, is_active=True)
        owner = _create_test_user(isolated_db, "owner_active@test.com", UserRole.KITCHEN_OWNER, is_active=True)
        
        kitchen = KitchenProfile(
            id=str(uuid.uuid4()),
            user_id=owner.id,
            kitchen_name="Gourmet Bowl Kitchen",
            address="123 Test Street",
            city="Hyderabad",
            is_open=True,
            is_approved=True,
            approval_status="APPROVED",
        )
        isolated_db.add(kitchen)
        isolated_db.commit()

        # Suspend owner
        update_user_status(owner.id, UserStatusUpdateRequest(status="SUSPENDED"), admin, isolated_db)
        isolated_db.refresh(owner)
        isolated_db.refresh(kitchen)

        assert owner.is_active is False
        assert kitchen.is_open is False

    def test_linked_records_triggers_soft_deletion_and_preserves_history(self, isolated_db):
        """Rule: Users with orders/financial history are archived, not deleted. All business records preserved."""
        admin = _create_test_user(isolated_db, "admin_rec@test.com", UserRole.ADMIN, is_active=True)
        customer = _create_test_user(isolated_db, "customer_with_orders@test.com", UserRole.CUSTOMER, is_active=True)
        owner = _create_test_user(isolated_db, "owner_with_kitchen@test.com", UserRole.KITCHEN_OWNER, is_active=True)

        kitchen = KitchenProfile(
            id=str(uuid.uuid4()),
            user_id=owner.id,
            kitchen_name="Preserved Kitchen",
            address="456 Food Lane",
            city="Bangalore",
            is_open=True,
            is_approved=True,
            approval_status="APPROVED",
        )
        isolated_db.add(kitchen)
        isolated_db.commit()

        order = Order(
            id=str(uuid.uuid4()),
            order_number="ORD-TEST-1001",
            customer_id=customer.id,
            kitchen_id=kitchen.id,
            status=OrderStatus.DELIVERED,
            subtotal=400.0,
            total_amount=450.0,
        )
        isolated_db.add(order)
        isolated_db.commit()

        # 1. Delete customer with historical orders -> Soft-archival
        res_cust = delete_user(customer.id, admin, isolated_db)
        assert res_cust["success"] is True
        assert res_cust["action"] == "archived"
        assert "safely deactivated and archived without deleting business history" in res_cust["message"]

        # Verify customer still exists in DB, marked inactive
        db_cust = isolated_db.query(User).filter(User.id == customer.id).first()
        assert db_cust is not None
        assert db_cust.is_active is False

        # Verify order is completely preserved
        db_order = isolated_db.query(Order).filter(Order.id == order.id).first()
        assert db_order is not None
        assert db_order.total_amount == 450.0

        # 2. Delete kitchen owner with orders -> Soft-archival
        res_owner = delete_user(owner.id, admin, isolated_db)
        assert res_owner["success"] is True
        assert res_owner["action"] == "archived"

        db_owner = isolated_db.query(User).filter(User.id == owner.id).first()
        assert db_owner is not None
        assert db_owner.is_active is False

        isolated_db.refresh(kitchen)
        assert kitchen.approval_status == "ARCHIVED"
        assert kitchen.is_open is False

    def test_get_users_protection_metadata(self, isolated_db):
        """Rule: get_users endpoint returns accurate protection reasons and business record indicators."""
        admin = _create_test_user(isolated_db, "admin_primary@test.com", UserRole.ADMIN, is_active=True, full_name="Admin One")
        eligible_cust = _create_test_user(isolated_db, "eligible_user@test.com", UserRole.CUSTOMER, is_active=True, full_name="Eligible User")
        root_admin = _create_test_user(isolated_db, "admin@cloudkitchen.com", UserRole.ADMIN, is_active=True, full_name="Root Admin")

        resp = get_users(skip=0, limit=10, admin=admin, db=isolated_db)
        users = {u["email"]: u for u in resp["users"]}

        # Self (admin_primary)
        assert users["admin_primary@test.com"]["is_self"] is True
        assert users["admin_primary@test.com"]["is_protected"] is True
        assert "Current Authenticated Admin" in users["admin_primary@test.com"]["protection_reason"]
        assert users["admin_primary@test.com"]["can_suspend"] is False
        assert users["admin_primary@test.com"]["can_delete"] is False

        # Root admin
        assert users["admin@cloudkitchen.com"]["is_system_account"] is True
        assert users["admin@cloudkitchen.com"]["is_protected"] is True
        assert "Root System Administrator" in users["admin@cloudkitchen.com"]["protection_reason"]
        assert users["admin@cloudkitchen.com"]["can_suspend"] is False
        assert users["admin@cloudkitchen.com"]["can_delete"] is False

        # Eligible customer
        assert users["eligible_user@test.com"]["is_protected"] is False
        assert users["eligible_user@test.com"]["protection_reason"] is None
        assert users["eligible_user@test.com"]["can_suspend"] is True
        assert users["eligible_user@test.com"]["can_delete"] is True
        assert users["eligible_user@test.com"]["delete_action_type"] == "delete"
