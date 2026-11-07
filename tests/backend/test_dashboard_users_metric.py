"""
Automated Integration Tests for Admin Dashboard Total Users Metric.
Verifies:
- total_users counts Customer and Kitchen Owner accounts ONLY
- All ADMIN accounts are strictly excluded from the total_users count in database calculation
- Dynamically calculated from database (never hardcoded)
- Adding an Admin account does NOT increment total_users
- Adding a Customer or Kitchen Owner account dynamically increments total_users
- Customers, Kitchen Owners, and Kitchens counts remain accurate and separate
- Does not modify, delete, or suspend any real accounts
"""
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.core.security import get_password_hash
from backend.app.models.enums import UserRole
from backend.app.models.user import User, KitchenProfile


@pytest.fixture
def dashboard_users_seed(db_session: Session):
    """Seed a known isolated set of users in the test session."""
    # 2 Admin accounts
    admin1 = User(
        id=str(uuid.uuid4()),
        email="test.superadmin@example.com",
        hashed_password=get_password_hash("AdminPass123!"),
        full_name="Super Admin One",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    admin2 = User(
        id=str(uuid.uuid4()),
        email="test.opsadmin@example.com",
        hashed_password=get_password_hash("AdminPass123!"),
        full_name="Ops Admin Two",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    # 3 Customer accounts
    c1 = User(
        id=str(uuid.uuid4()),
        email="test.cust1@example.com",
        hashed_password=get_password_hash("CustPass123!"),
        full_name="Customer One",
        role=UserRole.CUSTOMER,
        is_active=True,
        is_verified=True,
    )
    c2 = User(
        id=str(uuid.uuid4()),
        email="test.cust2@example.com",
        hashed_password=get_password_hash("CustPass123!"),
        full_name="Customer Two",
        role=UserRole.CUSTOMER,
        is_active=True,
        is_verified=True,
    )
    c3 = User(
        id=str(uuid.uuid4()),
        email="test.cust3@example.com",
        hashed_password=get_password_hash("CustPass123!"),
        full_name="Customer Three",
        role=UserRole.CUSTOMER,
        is_active=True,
        is_verified=True,
    )
    # 2 Kitchen Owner accounts
    ko1 = User(
        id=str(uuid.uuid4()),
        email="test.owner1@example.com",
        hashed_password=get_password_hash("OwnerPass123!"),
        full_name="Owner One",
        role=UserRole.KITCHEN_OWNER,
        is_active=True,
        is_verified=True,
    )
    ko2 = User(
        id=str(uuid.uuid4()),
        email="test.owner2@example.com",
        hashed_password=get_password_hash("OwnerPass123!"),
        full_name="Owner Two",
        role=UserRole.KITCHEN_OWNER,
        is_active=True,
        is_verified=True,
    )
    db_session.add_all([admin1, admin2, c1, c2, c3, ko1, ko2])
    db_session.flush()

    # Kitchen Profiles
    k1 = KitchenProfile(
        user_id=ko1.id,
        kitchen_name="Test Kitchen 1",
        address="Address 1",
        city="Bengaluru",
        is_open=True,
        is_approved=True,
    )
    k2 = KitchenProfile(
        user_id=ko2.id,
        kitchen_name="Test Kitchen 2",
        address="Address 2",
        city="Bengaluru",
        is_open=True,
        is_approved=True,
    )
    db_session.add_all([k1, k2])
    db_session.commit()

    return {
        "admin": admin1,
        "admin2": admin2,
        "customers": [c1, c2, c3],
        "owners": [ko1, ko2],
        "kitchens": [k1, k2],
    }


def test_total_users_excludes_admins(client: TestClient, dashboard_users_seed, db_session: Session):
    data = dashboard_users_seed

    # Login as admin
    login_res = client.post("/api/v1/auth/login", json={
        "email": data["admin"].email,
        "password": "AdminPass123!"
    })
    assert login_res.status_code == 200
    cookie = login_res.cookies.get(settings.SESSION_COOKIE_NAME)
    client.cookies.set(settings.SESSION_COOKIE_NAME, cookie)

    # Fetch dashboard statistics
    stats_res = client.get("/api/v1/admin/dashboard")
    assert stats_res.status_code == 200
    stats = stats_res.json()

    # Total in DB: 2 Admins + 3 Customers + 2 Kitchen Owners = 7 users total
    # But total_users MUST ONLY count customers + kitchen owners = 5
    assert stats["customers"] == 3
    assert stats["kitchen_owners"] == 2
    assert stats["total_users"] == 5
    assert stats["total_users"] == stats["customers"] + stats["kitchen_owners"]
    assert stats["kitchens"] == 2


def test_adding_admin_does_not_change_total_users(client: TestClient, dashboard_users_seed, db_session: Session):
    data = dashboard_users_seed

    # Login as admin
    login_res = client.post("/api/v1/auth/login", json={
        "email": data["admin"].email,
        "password": "AdminPass123!"
    })
    assert login_res.status_code == 200
    cookie = login_res.cookies.get(settings.SESSION_COOKIE_NAME)
    client.cookies.set(settings.SESSION_COOKIE_NAME, cookie)

    initial_stats = client.get("/api/v1/admin/dashboard").json()
    initial_total_users = initial_stats["total_users"]

    # Add a 3rd admin account
    admin3 = User(
        id=str(uuid.uuid4()),
        email="test.thirdadmin@example.com",
        hashed_password=get_password_hash("AdminPass123!"),
        full_name="Third Administrator",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    db_session.add(admin3)
    db_session.commit()

    # Re-fetch stats: total_users must NOT have increased!
    new_stats = client.get("/api/v1/admin/dashboard").json()
    assert new_stats["total_users"] == initial_total_users


def test_dynamic_increment_on_new_customer_and_owner(client: TestClient, dashboard_users_seed, db_session: Session):
    data = dashboard_users_seed

    login_res = client.post("/api/v1/auth/login", json={
        "email": data["admin"].email,
        "password": "AdminPass123!"
    })
    cookie = login_res.cookies.get(settings.SESSION_COOKIE_NAME)
    client.cookies.set(settings.SESSION_COOKIE_NAME, cookie)

    before_stats = client.get("/api/v1/admin/dashboard").json()
    prev_total = before_stats["total_users"]
    prev_customers = before_stats["customers"]
    prev_owners = before_stats["kitchen_owners"]

    # Add a new Customer
    new_c = User(
        id=str(uuid.uuid4()),
        email="test.fourthcust@example.com",
        hashed_password=get_password_hash("CustPass123!"),
        full_name="Fourth Customer",
        role=UserRole.CUSTOMER,
        is_active=True,
        is_verified=True,
    )
    db_session.add(new_c)
    db_session.commit()

    stats_after_c = client.get("/api/v1/admin/dashboard").json()
    assert stats_after_c["total_users"] == prev_total + 1
    assert stats_after_c["customers"] == prev_customers + 1
    assert stats_after_c["kitchen_owners"] == prev_owners

    # Add a new Kitchen Owner
    new_o = User(
        id=str(uuid.uuid4()),
        email="test.thirdowner@example.com",
        hashed_password=get_password_hash("OwnerPass123!"),
        full_name="Third Owner",
        role=UserRole.KITCHEN_OWNER,
        is_active=True,
        is_verified=True,
    )
    db_session.add(new_o)
    db_session.commit()

    stats_after_o = client.get("/api/v1/admin/dashboard").json()
    assert stats_after_o["total_users"] == prev_total + 2
    assert stats_after_o["customers"] == prev_customers + 1
    assert stats_after_o["kitchen_owners"] == prev_owners + 1


def test_removing_customer_and_owner_decrements_total_users(client: TestClient, dashboard_users_seed, db_session: Session):
    """Removing a Customer or Kitchen Owner dynamically decrements total_users and the respective sub-metric."""
    data = dashboard_users_seed

    login_res = client.post("/api/v1/auth/login", json={
        "email": data["admin"].email,
        "password": "AdminPass123!"
    })
    cookie = login_res.cookies.get(settings.SESSION_COOKIE_NAME)
    client.cookies.set(settings.SESSION_COOKIE_NAME, cookie)

    initial_stats = client.get("/api/v1/admin/dashboard").json()
    initial_total = initial_stats["total_users"]
    initial_cust = initial_stats["customers"]
    initial_owners = initial_stats["kitchen_owners"]

    # 1. Delete one customer
    cust_to_remove = data["customers"][0]
    db_session.delete(cust_to_remove)
    db_session.commit()

    stats_after_cust_del = client.get("/api/v1/admin/dashboard").json()
    assert stats_after_cust_del["total_users"] == initial_total - 1
    assert stats_after_cust_del["customers"] == initial_cust - 1
    assert stats_after_cust_del["kitchen_owners"] == initial_owners
    assert stats_after_cust_del["total_users"] == stats_after_cust_del["customers"] + stats_after_cust_del["kitchen_owners"]

    # 2. Delete one kitchen owner (along with their kitchen profile)
    owner_to_remove = data["owners"][0]
    kitchen_to_remove = next(k for k in data["kitchens"] if k.user_id == owner_to_remove.id)
    db_session.delete(kitchen_to_remove)
    db_session.delete(owner_to_remove)
    db_session.commit()

    stats_after_owner_del = client.get("/api/v1/admin/dashboard").json()
    assert stats_after_owner_del["total_users"] == initial_total - 2
    assert stats_after_owner_del["customers"] == initial_cust - 1
    assert stats_after_owner_del["kitchen_owners"] == initial_owners - 1
    assert stats_after_owner_del["total_users"] == stats_after_owner_del["customers"] + stats_after_owner_del["kitchen_owners"]


def test_removing_admin_does_not_affect_total_users(client: TestClient, dashboard_users_seed, db_session: Session):
    """Removing an Admin account does NOT change total_users, customers, or kitchen_owners."""
    data = dashboard_users_seed

    login_res = client.post("/api/v1/auth/login", json={
        "email": data["admin"].email,
        "password": "AdminPass123!"
    })
    cookie = login_res.cookies.get(settings.SESSION_COOKIE_NAME)
    client.cookies.set(settings.SESSION_COOKIE_NAME, cookie)

    initial_stats = client.get("/api/v1/admin/dashboard").json()
    expected_total = initial_stats["total_users"]
    expected_cust = initial_stats["customers"]
    expected_owners = initial_stats["kitchen_owners"]

    # Delete secondary admin (data["admin2"])
    admin2 = data["admin2"]
    db_session.delete(admin2)
    db_session.commit()

    stats_after_admin_del = client.get("/api/v1/admin/dashboard").json()
    assert stats_after_admin_del["total_users"] == expected_total
    assert stats_after_admin_del["customers"] == expected_cust
    assert stats_after_admin_del["kitchen_owners"] == expected_owners


def test_role_change_dynamically_updates_total_users(client: TestClient, dashboard_users_seed, db_session: Session):
    """When a user's role changes, total_users and sub-metrics update dynamically and remain consistent."""
    data = dashboard_users_seed

    login_res = client.post("/api/v1/auth/login", json={
        "email": data["admin"].email,
        "password": "AdminPass123!"
    })
    cookie = login_res.cookies.get(settings.SESSION_COOKIE_NAME)
    client.cookies.set(settings.SESSION_COOKIE_NAME, cookie)

    initial_stats = client.get("/api/v1/admin/dashboard").json()
    init_total = initial_stats["total_users"]
    init_cust = initial_stats["customers"]
    init_owners = initial_stats["kitchen_owners"]

    # 1. Promote Customer to ADMIN -> total_users must decrement by 1, customers must decrement by 1
    cust = data["customers"][0]
    cust.role = UserRole.ADMIN
    db_session.commit()

    stats1 = client.get("/api/v1/admin/dashboard").json()
    assert stats1["total_users"] == init_total - 1
    assert stats1["customers"] == init_cust - 1
    assert stats1["kitchen_owners"] == init_owners

    # 2. Demote Admin to CUSTOMER -> total_users must increment back, customers must increment back
    cust.role = UserRole.CUSTOMER
    db_session.commit()

    stats2 = client.get("/api/v1/admin/dashboard").json()
    assert stats2["total_users"] == init_total
    assert stats2["customers"] == init_cust
    assert stats2["kitchen_owners"] == init_owners

    # 3. Change Customer to KITCHEN_OWNER -> total_users remains unchanged, customers -1, kitchen_owners +1
    cust.role = UserRole.KITCHEN_OWNER
    db_session.commit()

    stats3 = client.get("/api/v1/admin/dashboard").json()
    assert stats3["total_users"] == init_total
    assert stats3["customers"] == init_cust - 1
    assert stats3["kitchen_owners"] == init_owners + 1
    assert stats3["total_users"] == stats3["customers"] + stats3["kitchen_owners"]


def test_registration_via_api_increments_total_users(client: TestClient, dashboard_users_seed, db_session: Session):
    """Registering a new customer via public auth API automatically increments total_users."""
    data = dashboard_users_seed

    # Login as admin to check before
    login_res = client.post("/api/v1/auth/login", json={
        "email": data["admin"].email,
        "password": "AdminPass123!"
    })
    cookie = login_res.cookies.get(settings.SESSION_COOKIE_NAME)
    client.cookies.set(settings.SESSION_COOKIE_NAME, cookie)

    before_stats = client.get("/api/v1/admin/dashboard").json()
    before_total = before_stats["total_users"]
    before_cust = before_stats["customers"]

    # Register new customer via public API
    reg_res = client.post("/api/v1/auth/register", json={
        "email": "new.api.customer@example.com",
        "password": "ValidPass123!",
        "full_name": "API Registered Customer",
        "phone_number": "+919876543210",
        "role": "CUSTOMER",
    })
    assert reg_res.status_code in [200, 201]

    # Re-check admin dashboard
    client.cookies.set(settings.SESSION_COOKIE_NAME, cookie)
    after_stats = client.get("/api/v1/admin/dashboard").json()
    assert after_stats["total_users"] == before_total + 1
    assert after_stats["customers"] == before_cust + 1
    assert after_stats["total_users"] == after_stats["customers"] + after_stats["kitchen_owners"]
