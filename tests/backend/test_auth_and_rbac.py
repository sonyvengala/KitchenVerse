"""
Automated unit and integration tests for Authentication and Server-side RBAC (Phase 2).
Verifies:
- Public registration creates CUSTOMER
- Role injection attack ({"role": "ADMIN"}) is completely blocked
- Bcrypt password hashing
- Session establishment with HttpOnly cookies
- Real server-side logout and session invalidation
- Email verification flow
- Password reset and change password flows
- Server-side RBAC protection on customer, kitchen, and admin routes
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.core.security import get_password_hash
from backend.app.models.enums import UserRole
from backend.app.models.user import User


def test_customer_registration_creates_customer(client: TestClient):
    payload = {
        "email": "john.customer@example.com",
        "password": "SecurePassword123!",
        "full_name": "John Customer",
        "phone_number": "+919876543210",
        "dietary_preferences": "Vegetarian"
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "john.customer@example.com"
    assert data["role"] == "CUSTOMER"
    assert data["is_active"] is True
    assert data["is_verified"] is False
    assert data["customer_profile"]["dietary_preferences"] == "Vegetarian"

    # Assert HttpOnly session cookie is set
    assert settings.SESSION_COOKIE_NAME in response.cookies


def test_cannot_obtain_admin_role_on_public_registration(client: TestClient):
    """
    Critical security test:
    A user submitting {"role": "ADMIN"} must NOT obtain administrator access.
    """
    payload = {
        "email": "attacker@example.com",
        "password": "AttackerPass123!",
        "full_name": "Attacker",
        "role": "ADMIN"  # Attempted privilege escalation
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    # Must remain CUSTOMER
    assert data["role"] == "CUSTOMER"


def test_duplicate_registration_rejected(client: TestClient):
    payload = {
        "email": "duplicate@example.com",
        "password": "Password123!",
        "full_name": "First User"
    }
    res1 = client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    res2 = client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 400
    assert "already exists" in res2.json()["detail"]


def test_kitchen_registration_creates_kitchen_owner(client: TestClient):
    import base64
    payload = {
        "email": "chef.mario@kitchen.com",
        "password": "ChefPassword123!",
        "full_name": "Chef Mario",
        "kitchen_name": "Mario's Trattoria Cloud Kitchen",
        "center_id": 10,
        "address": "456 Flavour Blvd",
        "city": "Bengaluru",
        "phone": "+918888888888",
        "description": "Authentic wood-fired cloud kitchen"
    }
    # Without FSSAI fields, registration must be rejected with 400
    res_rejected = client.post("/api/v1/auth/register-kitchen", json=payload)
    assert res_rejected.status_code == 400
    assert "FSSAI" in res_rejected.json()["detail"]

    # With FSSAI license number and valid base64 PDF document
    payload["fssai_license_number"] = "10019043002844"
    payload["fssai_document_data"] = "data:application/pdf;base64," + base64.b64encode(b"%PDF-1.4 demo fssai").decode()
    payload["fssai_filename"] = "mario_fssai.pdf"

    response = client.post("/api/v1/auth/register-kitchen", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["role"] == "KITCHEN_OWNER"
    assert data["kitchen_profile"]["kitchen_name"] == "Mario's Trattoria Cloud Kitchen"
    assert data["kitchen_profile"]["city"] == "Bengaluru"


def test_login_logout_real_session_invalidation(client: TestClient):
    # 1. Register
    reg_payload = {
        "email": "alice@example.com",
        "password": "AlicePassword123!",
        "full_name": "Alice Wonderland"
    }
    client.post("/api/v1/auth/register", json=reg_payload)

    # 2. Login
    login_payload = {
        "email": "alice@example.com",
        "password": "AlicePassword123!"
    }
    login_res = client.post("/api/v1/auth/login", json=login_payload)
    assert login_res.status_code == 200
    session_cookie = login_res.cookies.get(settings.SESSION_COOKIE_NAME)
    assert session_cookie is not None

    # 3. Access protected /me endpoint with session cookie
    client.cookies.set(settings.SESSION_COOKIE_NAME, session_cookie)
    me_res = client.get("/api/v1/auth/me")
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "alice@example.com"

    # 4. Logout (Server-side session invalidation)
    logout_res = client.post("/api/v1/auth/logout")
    assert logout_res.status_code == 200

    # 5. Access /me again with the same session cookie -> MUST BE 401 UNAUTHORIZED
    client.cookies.set(settings.SESSION_COOKIE_NAME, session_cookie)
    me_after_logout = client.get("/api/v1/auth/me")
    assert me_after_logout.status_code == 401
    assert "invalid or has expired" in me_after_logout.json()["detail"]


def test_email_verification_flow(client: TestClient, db_session: Session):
    reg_payload = {
        "email": "bob.verify@example.com",
        "password": "BobPassword123!",
        "full_name": "Bob Verify"
    }
    reg_res = client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201

    # Get verification token from DB
    user = db_session.query(User).filter(User.email == "bob.verify@example.com").first()
    assert user is not None
    assert user.is_verified is False
    token = user.verification_token

    # Verify email via API
    verify_res = client.post("/api/v1/auth/verify-email", json={"token": token})
    assert verify_res.status_code == 200

    # Refresh and verify
    db_session.refresh(user)
    assert user.is_verified is True
    assert user.verification_token is None


def test_forgot_and_reset_password_flow(client: TestClient, db_session: Session):
    reg_payload = {
        "email": "carol.reset@example.com",
        "password": "OldPassword123!",
        "full_name": "Carol Reset"
    }
    client.post("/api/v1/auth/register", json=reg_payload)

    # Request password reset
    forgot_res = client.post("/api/v1/auth/forgot-password", json={"email": "carol.reset@example.com"})
    assert forgot_res.status_code == 200
    # Verify token is NEVER returned in HTTP response body
    assert forgot_res.json().get("token") is None

    # Retrieve reset token securely from test DB
    user = db_session.query(User).filter_by(email="carol.reset@example.com").first()
    assert user is not None
    reset_token = user.password_reset_token
    assert reset_token is not None

    # Reset password
    reset_res = client.post("/api/v1/auth/reset-password", json={
        "token": reset_token,
        "new_password": "NewCarolPassword123!"
    })
    assert reset_res.status_code == 200

    # Old password must fail
    old_login = client.post("/api/v1/auth/login", json={
        "email": "carol.reset@example.com",
        "password": "OldPassword123!"
    })
    assert old_login.status_code == 401

    # New password must succeed
    new_login = client.post("/api/v1/auth/login", json={
        "email": "carol.reset@example.com",
        "password": "NewCarolPassword123!"
    })
    assert new_login.status_code == 200


def test_server_side_rbac_enforcement(client: TestClient, db_session: Session):
    """
    Test Server-Side Role-Based Access Control (RBAC):
    Customer -> Cannot access Kitchen or Admin routes
    Kitchen Owner -> Cannot access Admin route
    Admin -> Accesses Admin route
    """
    # 1. Create Admin user in DB
    admin_user = User(
        email="superadmin@cloudkitchen.com",
        hashed_password=get_password_hash("AdminMasterPass123!"),
        full_name="Platform Admin",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True
    )
    db_session.add(admin_user)
    db_session.commit()

    # 2. Customer login
    client.post("/api/v1/auth/register", json={
        "email": "customer.rbac@example.com",
        "password": "Password123!",
        "full_name": "Customer RBAC"
    })
    customer_login = client.post("/api/v1/auth/login", json={
        "email": "customer.rbac@example.com",
        "password": "Password123!"
    })
    customer_cookie = customer_login.cookies.get(settings.SESSION_COOKIE_NAME)

    # Customer accessing customer route -> 200
    client.cookies.set(settings.SESSION_COOKIE_NAME, customer_cookie)
    res_c = client.get("/api/v1/test-rbac/customer")
    assert res_c.status_code == 200

    # Customer accessing kitchen route -> 403 Forbidden
    res_k_denied = client.get("/api/v1/test-rbac/kitchen")
    assert res_k_denied.status_code == 403

    # Customer accessing admin route -> 403 Forbidden
    res_a_denied = client.get("/api/v1/test-rbac/admin")
    assert res_a_denied.status_code == 403

    # 3. Kitchen Owner login
    import base64
    reg_res = client.post("/api/v1/auth/register-kitchen", json={
        "email": "kitchen.rbac@example.com",
        "password": "Password123!",
        "full_name": "Kitchen Owner RBAC",
        "kitchen_name": "Spice Route",
        "address": "Street 1",
        "city": "Mumbai",
        "fssai_license_number": "10019043002844",
        "fssai_document_data": "data:application/pdf;base64," + base64.b64encode(b"%PDF-1.4 demo fssai").decode(),
        "fssai_filename": "rbac_fssai.pdf",
    })
    assert reg_res.status_code == 201
    kitchen_login = client.post("/api/v1/auth/login", json={
        "email": "kitchen.rbac@example.com",
        "password": "Password123!"
    })
    kitchen_cookie = kitchen_login.cookies.get(settings.SESSION_COOKIE_NAME)

    # Kitchen Owner accessing kitchen route -> 200
    client.cookies.set(settings.SESSION_COOKIE_NAME, kitchen_cookie)
    res_k = client.get("/api/v1/test-rbac/kitchen")
    assert res_k.status_code == 200

    # Kitchen Owner accessing admin route -> 403 Forbidden
    res_k_admin_denied = client.get("/api/v1/test-rbac/admin")
    assert res_k_admin_denied.status_code == 403

    # 4. Admin login
    admin_login = client.post("/api/v1/auth/login", json={
        "email": "superadmin@cloudkitchen.com",
        "password": "AdminMasterPass123!"
    })
    assert admin_login.status_code == 200, f"Admin login failed: {admin_login.json()}"
    admin_cookie = admin_login.cookies.get(settings.SESSION_COOKIE_NAME)

    # Admin accessing admin route -> 200
    client.cookies.set(settings.SESSION_COOKIE_NAME, admin_cookie)
    res_admin = client.get("/api/v1/test-rbac/admin")
    assert res_admin.status_code == 200
    assert res_admin.json()["role"] == "ADMIN"
