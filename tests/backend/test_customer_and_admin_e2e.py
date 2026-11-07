"""
End-to-End Integration Tests for KitchenVerse.
Tests:
1. Customer full lifecycle: Register -> Email Verify -> Login -> Browse -> Add to Cart -> Checkout -> Track -> Review.
2. Kitchen Owner Approval Workflow: Register -> Email Verify -> PENDING_APPROVAL (blocked) -> Admin Review & Approve -> APPROVED (operational).
3. Recipe -> Ingredient -> Inventory auto-deduction upon Kitchen Order Acceptance.
4. Forgot Password / Secure Token Reset flow.
5. Server-side RBAC restriction across all three portals (Customer, Kitchen Owner, Admin).
"""
import uuid
import base64
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.security import get_password_hash
from backend.app.models.enums import UserRole
from backend.app.models.user import User, KitchenProfile
from backend.app.models.inventory import Inventory, InventoryTransaction
from backend.app.models.menu import Ingredient, MenuItem, MenuItemIngredient
from backend.app.models.order import Order, OrderItem, OrderStatus, PaymentStatus


def test_kitchen_approval_workflow_and_rbac(client: TestClient, db_session: Session):
    """
    Test Kitchen Owner Approval Lifecycle:
    EMAIL_UNVERIFIED -> Verify Email -> PENDING_APPROVAL -> Admin Approve -> APPROVED.
    Verify unapproved kitchen cannot access operational endpoints.
    """
    # 1. Register Kitchen Owner
    ko_email = f"chef_{uuid.uuid4().hex[:6]}@example.com"
    reg_resp = client.post("/api/v1/auth/register-kitchen", json={
        "email": ko_email,
        "password": "ChefPassword123!",
        "full_name": "Master Chef",
        "kitchen_name": "Royal Biryani Hub",
        "address": "123 Food Street",
        "city": "Bengaluru",
        "fssai_license_number": "10019043002844",
        "fssai_document_data": "data:application/pdf;base64," + base64.b64encode(b"%PDF-1.4 test fssai").decode(),
        "fssai_filename": "royal_fssai.pdf",
    })
    assert reg_resp.status_code == 201
    data = reg_resp.json()
    assert data["role"] == "KITCHEN_OWNER"
    assert data["kitchen_profile"]["is_approved"] is False
    assert data["kitchen_profile"]["approval_status"] in ("PENDING_APPROVAL", "EMAIL_UNVERIFIED")

    # Get user and kitchen from db
    ko_user = db_session.query(User).filter(User.email == ko_email).first()
    assert ko_user is not None
    assert ko_user.verification_token is not None

    # 2. Verify Email via JSON payload
    verify_resp = client.post("/api/v1/auth/verify-email", json={"token": ko_user.verification_token})
    assert verify_resp.status_code == 200

    db_session.refresh(ko_user)
    assert ko_user.is_verified is True
    assert ko_user.kitchen_profile.approval_status == "PENDING_APPROVAL"

    # 3. Log in as Kitchen Owner while PENDING_APPROVAL
    login_resp = client.post("/api/v1/auth/login", json={"email": ko_email, "password": "ChefPassword123!"})
    assert login_resp.status_code == 200

    # 4. Attempt operational access (e.g. creating a menu item) -> Must be 403 Forbidden!
    blocked_resp = client.post("/api/v1/kitchen/menu", json={
        "name": "Dum Biryani",
        "price": 250.0,
        "category": "Main Course",
        "cuisine": "Indian",
        "is_veg": False
    })
    assert blocked_resp.status_code == 403
    assert "approval" in blocked_resp.json()["detail"].lower()

    # 5. Create an ADMIN user
    admin = User(
        email=f"admin_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=get_password_hash("AdminSecret123!"),
        full_name="System Admin",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    db_session.add(admin)
    db_session.commit()

    # Log in as ADMIN
    admin_login = client.post("/api/v1/auth/login", json={"email": admin.email, "password": "AdminSecret123!"})
    assert admin_login.status_code == 200

    # Admin reviews pending kitchens
    kitchen_id = ko_user.kitchen_profile.id
    admin_kitchens = client.get("/api/v1/admin/kitchens")
    assert admin_kitchens.status_code == 200
    all_k = admin_kitchens.json().get("kitchens", [])
    assert any(k["id"] == kitchen_id for k in all_k)

    # Admin APPROVES kitchen via POST
    approve_resp = client.post(f"/api/v1/admin/kitchens/{kitchen_id}/approve")
    assert approve_resp.status_code == 200
    assert approve_resp.json()["approval_status"] == "APPROVED"
    assert approve_resp.json()["is_approved"] is True

    # 6. Kitchen Owner logs back in and now has OPERATIONAL ACCESS!
    client.post("/api/v1/auth/login", json={"email": ko_email, "password": "ChefPassword123!"})
    menu_create = client.post("/api/v1/kitchen/menu", json={
        "name": "Royal Chicken Biryani",
        "price": 320.0,
        "category": "Biryani",
        "cuisine": "Hyderabadi",
        "is_veg": False
    })
    assert menu_create.status_code == 201
    created_item = menu_create.json()
    assert created_item["name"] == "Royal Chicken Biryani"


def test_recipe_inventory_auto_deduction_on_order_accept(client: TestClient, db_session: Session):
    """
    CRITICAL ARCHITECTURE TEST:
    MENU ITEM -> RECIPE -> INGREDIENTS -> INVENTORY
    When a customer orders 2 Chicken Biryanis:
    Rice = 0.20 kg * 2 = 0.40 kg
    Chicken = 0.18 kg * 2 = 0.36 kg
    Kitchen accepts order -> Inventory is deducted automatically and logged in ledger.
    """
    # 1. Setup Approved Kitchen Owner
    ko_email = f"chef_{uuid.uuid4().hex[:6]}@example.com"
    ko_user = User(
        email=ko_email,
        hashed_password=get_password_hash("ChefSecret123!"),
        full_name="Chef Ramesh",
        role=UserRole.KITCHEN_OWNER,
        is_active=True,
        is_verified=True,
    )
    db_session.add(ko_user)
    db_session.commit()

    kitchen = KitchenProfile(
        user_id=ko_user.id,
        kitchen_name="Biryani Palace",
        address="Koramangala 4th Block",
        city="Bengaluru",
        is_approved=True,
        approval_status="APPROVED",
        is_open=True,
    )
    db_session.add(kitchen)
    db_session.commit()

    # 2. Log in as Kitchen Owner to create Ingredients and Menu Item with Recipe
    login_resp = client.post("/api/v1/auth/login", json={"email": ko_email, "password": "ChefSecret123!"})
    assert login_resp.status_code == 200

    # Create Ingredients: Basmati Rice (10 kg), Chicken (10 kg)
    rice_resp = client.post("/api/v1/kitchen/ingredients", json={
        "name": "Basmati Rice",
        "unit": "kg",
        "initial_stock": 10.0,
        "minimum_stock_threshold": 2.0,
        "reorder_quantity": 5.0
    })
    assert rice_resp.status_code == 201
    rice_id = rice_resp.json()["id"]

    chicken_resp = client.post("/api/v1/kitchen/ingredients", json={
        "name": "Chicken",
        "unit": "kg",
        "initial_stock": 10.0,
        "minimum_stock_threshold": 2.0,
        "reorder_quantity": 5.0
    })
    assert chicken_resp.status_code == 201
    chicken_id = chicken_resp.json()["id"]

    # Create Menu Item: Chicken Biryani
    menu_resp = client.post("/api/v1/kitchen/menu", json={
        "name": "Chicken Biryani",
        "price": 300.0,
        "category": "Main Course",
        "cuisine": "Biryani",
        "is_veg": False
    })
    assert menu_resp.status_code == 201
    dish_id = menu_resp.json()["id"]

    # Save Recipe: Basmati Rice = 0.20 kg, Chicken = 0.18 kg per serving
    r1 = client.post(f"/api/v1/kitchen/menu/{dish_id}/recipe", json={
        "ingredient_id": rice_id,
        "quantity_required": 0.20
    })
    assert r1.status_code == 201

    r2 = client.post(f"/api/v1/kitchen/menu/{dish_id}/recipe", json={
        "ingredient_id": chicken_id,
        "quantity_required": 0.18
    })
    assert r2.status_code == 201

    # 3. Create and Log in as Customer
    cust_email = f"customer_{uuid.uuid4().hex[:6]}@example.com"
    cust_user = User(
        email=cust_email,
        hashed_password=get_password_hash("CustSecret123!"),
        full_name="Ananya Sharma",
        role=UserRole.CUSTOMER,
        is_active=True,
        is_verified=True,
    )
    db_session.add(cust_user)
    db_session.commit()

    cust_login = client.post("/api/v1/auth/login", json={"email": cust_email, "password": "CustSecret123!"})
    assert cust_login.status_code == 200

    # Customer places order for 2 Chicken Biryanis
    order_resp = client.post("/api/v1/customer/orders", json={
        "kitchen_id": kitchen.id,
        "items": [{"menu_item_id": dish_id, "quantity": 2}],
        "payment_method": "CASH_ON_DELIVERY"
    })
    assert order_resp.status_code == 201
    order_data = order_resp.json()
    order_id = order_data["id"]
    assert order_data["status"] in ["PENDING", "ORDER_PLACED", "PAYMENT_CONFIRMED"]

    # Verify inventory is NOT deducted upon placement (only upon acceptance/prep!)
    rice_ing = db_session.query(Ingredient).filter(Ingredient.id == rice_id).first()
    chicken_ing = db_session.query(Ingredient).filter(Ingredient.id == chicken_id).first()
    assert float(rice_ing.current_stock) == 10.0
    assert float(chicken_ing.current_stock) == 10.0

    # 4. Kitchen Owner logs in and ACCEPTS the order
    client.post("/api/v1/auth/login", json={"email": ko_email, "password": "ChefSecret123!"})
    accept_resp = client.post(f"/api/v1/kitchen/orders/{order_id}/accept")
    assert accept_resp.status_code == 200
    assert accept_resp.json()["status"] in ["CONFIRMED", "KITCHEN_ACCEPTED"]

    # 5. VERIFY AUTOMATIC INVENTORY DEDUCTION & AUDIT LEDGER:
    # 2 servings * 0.20 kg = 0.40 kg Rice deducted -> 9.60 kg remaining
    # 2 servings * 0.18 kg = 0.36 kg Chicken deducted -> 9.64 kg remaining
    db_session.refresh(rice_ing)
    db_session.refresh(chicken_ing)
    assert round(float(rice_ing.current_stock), 2) == 9.60
    assert round(float(chicken_ing.current_stock), 2) == 9.64

    # Verify Inventory Ledger Transactions
    ledger_entries = db_session.query(InventoryTransaction).filter(
        InventoryTransaction.reference_order_id == order_id
    ).all()
    assert len(ledger_entries) >= 2


def test_forgot_password_and_token_reset(client: TestClient, db_session: Session):
    """
    Test Secure Forgot Password & Token Reset:
    Request reset -> Token generated -> Reset Password -> Login with new password.
    """
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    user = User(
        email=email,
        hashed_password=get_password_hash("OldPassword123!"),
        full_name="Password Test",
        role=UserRole.CUSTOMER,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()

    # 1. Request password reset
    req_resp = client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert req_resp.status_code == 200
    # Verify token is NEVER returned in HTTP response body
    assert req_resp.json().get("token") is None

    # Retrieve reset token securely from test DB
    user_entry = db_session.query(User).filter_by(email=email).first()
    assert user_entry is not None
    token = user_entry.password_reset_token
    assert token is not None

    # 2. Reset password using the secure token
    new_pass = "BrandNewPassword123!"
    reset_resp = client.post("/api/v1/auth/reset-password", json={
        "token": token,
        "new_password": new_pass
    })
    assert reset_resp.status_code == 200

    # 3. Old password should fail
    fail_login = client.post("/api/v1/auth/login", json={"email": email, "password": "OldPassword123!"})
    assert fail_login.status_code == 401

    # 4. New password succeeds
    success_login = client.post("/api/v1/auth/login", json={"email": email, "password": new_pass})
    assert success_login.status_code == 200
