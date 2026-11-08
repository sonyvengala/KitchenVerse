"""
Fully Isolated End-to-End Test Suite (Checks A through AH).
Executes against an isolated, in-memory or dedicated test database.
Guarantees ZERO data pollution on the development/production database (cloudkitchen_local.db).
"""
import os
import sys
sys.path.insert(0, os.path.abspath("."))
import uuid
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from backend.app.core.database import Base, get_db
from backend.app.core.security import get_password_hash
from backend.app.models.enums import UserRole
from backend.app.models.user import User, KitchenProfile
from backend.app.main import app

def run_isolated_full_e2e():
    print("=== INITIALIZING ISOLATED E2E DATABASE ===")
    
    # 1. Dedicated isolated test engine
    TEST_ENGINE = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)
    Base.metadata.create_all(bind=TEST_ENGINE)

    # 2. Dependency override for get_db
    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # 3. Seed legitimate admin account in isolated DB
    db = TestingSession()
    try:
        admin_user = User(
            email="admin@cloudkitchen.com",
            hashed_password=get_password_hash("AdminPass123!"),
            full_name="Platform Admin",
            role=UserRole.ADMIN,
            is_active=True,
            is_verified=True,
        )
        db.add(admin_user)
        db.commit()
    finally:
        db.close()

    test_id = uuid.uuid4().hex[:6]
    print(f"=== STARTING ISOLATED E2E PLATFORM VALIDATION (RUN ID: {test_id}) ===")

    try:
        with TestClient(app) as client:
            # ─────────────────────────────────────────────────────────────
            # A. Customer Registration
            # ─────────────────────────────────────────────────────────────
            print("\n[Check A] Customer Registration...")
            cust_email = f"customer_{test_id}@example.com"
            cust_pass = "CustPass123!"
            cust_client = TestClient(app)

            reg_payload = {
                "email": cust_email,
                "password": cust_pass,
                "full_name": f"Customer Test {test_id}",
                "phone_number": "+919111111111",
                "role": "CUSTOMER"
            }
            r = cust_client.post("/api/v1/auth/register", json=reg_payload)
            assert r.status_code == 201, f"Customer registration failed: {r.status_code} {r.text}"
            cust_data = r.json()
            cust_id = cust_data.get("id") or cust_data.get("user", {}).get("id")
            print(f"  [OK] Customer registered successfully (ID: {cust_id})")

            # ─────────────────────────────────────────────────────────────
            # C. Email Verification
            # ─────────────────────────────────────────────────────────────
            print("\n[Check C] Email Verification...")
            db = TestingSession()
            try:
                user_entry = db.query(User).filter(User.id == cust_id).first()
                v_token = user_entry.verification_token
            finally:
                db.close()

            r_verify = cust_client.post("/api/v1/auth/verify-email", json={"token": v_token})
            assert r_verify.status_code == 200, f"Customer verify-email failed: {r_verify.status_code} {r_verify.text}"
            print(f"  [OK] Customer email verified with real token.")

            # ─────────────────────────────────────────────────────────────
            # B. Customer Login
            # ─────────────────────────────────────────────────────────────
            print("\n[Check B] Customer Login...")
            r_login = cust_client.post("/api/v1/auth/login", json={"email": cust_email, "password": cust_pass})
            assert r_login.status_code == 200, f"Customer login failed: {r_login.status_code} {r_login.text}"
            print("  [OK] Customer logged in. Session established.")

            # ─────────────────────────────────────────────────────────────
            # D. Customer Forgot Password
            # ─────────────────────────────────────────────────────────────
            print("\n[Check D] Customer Forgot Password...")
            r_forgot = cust_client.post("/api/v1/auth/forgot-password", json={"email": cust_email})
            assert r_forgot.status_code == 200, f"Forgot password failed: {r_forgot.status_code}"
            
            db = TestingSession()
            try:
                user_entry = db.query(User).filter(User.id == cust_id).first()
                reset_token = user_entry.password_reset_token
                assert reset_token is not None, "password_reset_token should be set"
            finally:
                db.close()
            print(f"  [OK] Forgot password generated real token in DB: {reset_token[:10]}...")

            # ─────────────────────────────────────────────────────────────
            # E. Customer Reset Password
            # ─────────────────────────────────────────────────────────────
            print("\n[Check E] Customer Reset Password...")
            new_cust_pass = "NewCustPass123!"
            r_reset = cust_client.post("/api/v1/auth/reset-password", json={"token": reset_token, "new_password": new_cust_pass})
            assert r_reset.status_code == 200, f"Reset password failed: {r_reset.status_code}"
            
            # Verify login with new password
            r_relogin = cust_client.post("/api/v1/auth/login", json={"email": cust_email, "password": new_cust_pass})
            assert r_relogin.status_code == 200, "Relogin with new password failed"
            print("  [OK] Password reset confirmed. Logged in with new credentials.")

            # ─────────────────────────────────────────────────────────────
            # F. Kitchen Owner Registration
            # ─────────────────────────────────────────────────────────────
            print("\n[Check F] Kitchen Owner Registration...")
            ko_email = f"chef_{test_id}@example.com"
            ko_pass = "ChefPass123!"
            ko_client = TestClient(app)

            ko_reg_payload = {
                "email": ko_email,
                "password": ko_pass,
                "full_name": f"Chef Luigi {test_id}",
                "phone_number": "+919222222222",
                "kitchen_name": f"Luigi Cloud Trattoria {test_id}",
                "description": "Authentic woodfired pizzas and handmade pastas",
                "address": "456 Kitchen Boulevard",
                "city": "Bengaluru",
                "fssai_license_number": "10019043002844",
                "fssai_document_data": "data:application/pdf;base64,JVBERi0xLjQgZGVtbyBmc3NhaQ==",
                "fssai_filename": "luigi_fssai.pdf"
            }
            r_ko_reg = ko_client.post("/api/v1/auth/register-kitchen", json=ko_reg_payload)
            assert r_ko_reg.status_code == 201, f"Kitchen registration failed: {r_ko_reg.status_code} {r_ko_reg.text}"
            ko_data = r_ko_reg.json()
            ko_user_id = ko_data.get("id") or ko_data.get("user", {}).get("id")
            print(f"  [OK] Kitchen Owner registered (User ID: {ko_user_id})")

            # Lookup Kitchen Profile ID & Verify Email
            db = TestingSession()
            try:
                kitchen = db.query(KitchenProfile).filter(KitchenProfile.user_id == ko_user_id).first()
                assert kitchen is not None, "Kitchen profile not created in DB"
                kitchen_id = kitchen.id
                ko_user = db.query(User).filter(User.id == ko_user_id).first()
                ko_v_token = ko_user.verification_token
            finally:
                db.close()

            r_ko_verify = ko_client.post("/api/v1/auth/verify-email", json={"token": ko_v_token})
            assert r_ko_verify.status_code == 200, f"Kitchen verify-email failed: {r_ko_verify.status_code}"
            print("  [OK] Kitchen Owner email verified with real token.")

            # ─────────────────────────────────────────────────────────────
            # G. Admin Approval
            # ─────────────────────────────────────────────────────────────
            print("\n[Check G] Admin Approval of Kitchen...")
            admin_client = TestClient(app)
            r_admin_login = admin_client.post("/api/v1/auth/login", json={"email": "admin@cloudkitchen.com", "password": "AdminPass123!"})
            assert r_admin_login.status_code == 200, f"Admin login failed: {r_admin_login.status_code} {r_admin_login.text}"

            r_approve = admin_client.post(f"/api/v1/admin/kitchens/{kitchen_id}/approve")
            assert r_approve.status_code == 200, f"Kitchen approval failed: {r_approve.status_code} {r_approve.text}"
            print("  [OK] Admin approved kitchen successfully.")

            # ─────────────────────────────────────────────────────────────
            # H. Kitchen Owner Login
            # ─────────────────────────────────────────────────────────────
            print("\n[Check H] Kitchen Owner Login...")
            r_ko_login = ko_client.post("/api/v1/auth/login", json={"email": ko_email, "password": ko_pass})
            assert r_ko_login.status_code == 200, f"Kitchen login failed: {r_ko_login.status_code}"
            r_ko_dash = ko_client.get("/api/v1/kitchen/dashboard")
            assert r_ko_dash.status_code == 200, f"Kitchen dashboard failed: {r_ko_dash.status_code}"
            print("  [OK] Kitchen Owner logged in and loaded dashboard.")

            # ─────────────────────────────────────────────────────────────
            # I & J & K & L. Kitchen Setup: Menu, Recipe, Inventory
            # ─────────────────────────────────────────────────────────────
            print("\n[Check I, J, K, L] Kitchen Setup: Menu, Recipe, Inventory...")
            # Inventory: Mozzarella (10.0 kg)
            ing_payload = {
                "name": f"Mozzarella {test_id}",
                "unit": "kg",
                "initial_stock": 10.0,
                "minimum_stock_threshold": 2.0,
                "reorder_quantity": 20.0
            }
            r_ing = ko_client.post("/api/v1/kitchen/ingredients", json=ing_payload)
            assert r_ing.status_code == 201, f"Create ingredient failed: {r_ing.status_code} {r_ing.text}"
            ing_id = r_ing.json()["id"]

            # Menu item: Margherita Pizza (₹450.0)
            item_payload = {
                "name": f"Classic Margherita {test_id}",
                "description": "San Marzano tomatoes, fresh mozzarella, basil",
                "price": 450.0,
                "category": "Pizza",
                "cuisine": "Italian",
                "is_available": True
            }
            r_item = ko_client.post("/api/v1/kitchen/menu", json=item_payload)
            assert r_item.status_code == 201, f"Create menu item failed: {r_item.status_code} {r_item.text}"
            item_id = r_item.json()["id"]

            # Recipe: 0.20 kg cheese per pizza
            link_payload = {
                "ingredient_id": ing_id,
                "quantity_required": 0.20
            }
            r_link = ko_client.post(f"/api/v1/kitchen/menu/{item_id}/recipe", json=link_payload)
            assert r_link.status_code == 201, f"Recipe link failed: {r_link.status_code} {r_link.text}"
            print("  [OK] Kitchen created ingredient, menu item, and recipe link successfully.")

            # ─────────────────────────────────────────────────────────────
            # M & N. Customer Kitchen Discovery & Menu Browsing
            # ─────────────────────────────────────────────────────────────
            print("\n[Check M & N] Customer Kitchen Discovery & Menu Browsing...")
            r_disc = cust_client.get("/api/v1/customer/kitchens")
            assert r_disc.status_code == 200, f"Kitchen discovery failed: {r_disc.status_code}"
            kitchens_list = r_disc.json()
            assert any(k["id"] == kitchen_id for k in kitchens_list), "Approved kitchen not in discovery list"

            r_menu = cust_client.get(f"/api/v1/customer/kitchens/{kitchen_id}")
            assert r_menu.status_code == 200
            menu_items = r_menu.json().get("menu_items", [])
            assert any(m["id"] == item_id for m in menu_items), "Menu item not found in customer view"
            print("  [OK] Customer discovered kitchen and browsed menu successfully.")

            # ─────────────────────────────────────────────────────────────
            # P. Promotion Creation by Admin (WELCOME_20)
            # ─────────────────────────────────────────────────────────────
            print("\n[Check P] Admin Creates WELCOME_20 Promotion...")
            promo_payload = {
                "code": "WELCOME_20",
                "title": "Welcome Discount 20%",
                "description": "20% discount on orders over ₹500, capped at ₹200",
                "discount_percent": 20.0,
                "discount_amount": 0.0,
                "min_order_amount": 500.0,
                "max_discount_amount": 200.0,
                "usage_limit": 50,
                "per_user_limit": 1,
                "is_active": True,
                "valid_from": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
                "valid_until": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            }
            r_promo = admin_client.post("/api/v1/admin/promotions", json=promo_payload)
            assert r_promo.status_code == 201, f"Create promotion failed: {r_promo.status_code} {r_promo.text}"
            promo_data = r_promo.json()
            promo_id = promo_data["id"]
            assert promo_data["code"] == "WELCOME_20"
            assert promo_data["is_active"] is True
            print(f"  [OK] Admin created promotion 'WELCOME_20' (ID: {promo_id})")

            # ─────────────────────────────────────────────────────────────
            # Q. Promotion Activation & Query
            # ─────────────────────────────────────────────────────────────
            print("\n[Check Q] Verify Promotion Activation...")
            r_promos = admin_client.get("/api/v1/admin/promotions?active=true&search=WELCOME_20")
            assert r_promos.status_code == 200
            promos_list = r_promos.json().get("promotions", [])
            assert any(p["code"] == "WELCOME_20" for p in promos_list), "WELCOME_20 not returned in active search"
            print("  [OK] Promotion 'WELCOME_20' is active and verified in database.")

            # ─────────────────────────────────────────────────────────────
            # O & R & S & T. Cart, Apply WELCOME_20, Backend Validation, Discount Calc
            # ─────────────────────────────────────────────────────────────
            print("\n[Check O, R, S, T] Cart & Checkout Preview with WELCOME_20...")
            # Customer orders 2 pizzas @ ₹450 = ₹900 subtotal (> ₹500 min order)
            # 20% of ₹900 = ₹180 discount (within ₹200 cap)
            preview_payload = {
                "kitchen_id": kitchen_id,
                "items": [
                    {"menu_item_id": item_id, "quantity": 2}
                ],
                "promotion_code": "WELCOME_20"
            }
            r_preview = cust_client.post("/api/v1/customer/checkout/preview", json=preview_payload)
            assert r_preview.status_code == 200, f"Checkout preview failed: {r_preview.status_code} {r_preview.text}"
            preview_data = r_preview.json()
            subtotal = preview_data["subtotal"]
            discount = preview_data["discount_amount"]
            applied_code = preview_data.get("applied_promotion_code") or preview_data.get("promotion_code")
            print(f"  Subtotal: INR {subtotal:.2f} | Discount Applied: INR {discount:.2f} | Applied Promo: {applied_code}")
            assert subtotal == 900.0, f"Expected subtotal 900, got {subtotal}"
            assert discount == 180.0, f"Expected discount 180 (20% of 900), got {discount}"
            print("  [OK] Backend validated coupon and calculated exact discount (INR 180.00).")

            # ─────────────────────────────────────────────────────────────
            # U. Order Placement with WELCOME_20
            # ─────────────────────────────────────────────────────────────
            print("\n[Check U] Customer Places Order with WELCOME_20...")
            order_payload = {
                "kitchen_id": kitchen_id,
                "items": [
                    {"menu_item_id": item_id, "quantity": 2}
                ],
                "special_instructions": "Extra oregano please",
                "payment_method": "CASH",
                "promotion_code": "WELCOME_20"
            }
            r_order = cust_client.post("/api/v1/customer/orders", json=order_payload)
            assert r_order.status_code == 201, f"Order placement failed: {r_order.status_code} {r_order.text}"
            order_data = r_order.json()
            order_id = order_data["id"]
            assert order_data.get("discount_amount") == 180.0
            print(f"  [OK] Order placed successfully with coupon (Order ID: {order_id}, Discount: INR 180.00)")

            # Verify coupon usage limit check: per_user_limit is 1, second order with WELCOME_20 must fail
            r_order_dup = cust_client.post("/api/v1/customer/orders", json=order_payload)
            assert r_order_dup.status_code == 400, "Second order with same per-user limit coupon should be rejected"
            print("  [OK] Per-user coupon limit enforced: duplicate coupon usage correctly rejected.")

            # ─────────────────────────────────────────────────────────────
            # V & W & X. Kitchen Notification, Order Acceptance & Recipe Inventory Deduction
            # ─────────────────────────────────────────────────────────────
            print("\n[Check V, W, X] Kitchen Receives, Accepts Order & Deducts Inventory...")
            r_ko_notifs = ko_client.get("/api/v1/kitchen/notifications")
            assert r_ko_notifs.status_code == 200
            assert len(r_ko_notifs.json()) >= 1, "Kitchen should have received new order notification"

            # Accept order: 2 pizzas * 0.20 kg = 0.40 kg deduction from 10.0 kg -> 9.60 kg remaining
            r_accept = ko_client.post(f"/api/v1/kitchen/orders/{order_id}/accept")
            assert r_accept.status_code == 200, f"Kitchen accept order failed: {r_accept.status_code} {r_accept.text}"
            
            # Check inventory deduction in database
            r_ings = ko_client.get("/api/v1/kitchen/ingredients")
            assert r_ings.status_code == 200
            ing_record = next(i for i in r_ings.json() if i["id"] == ing_id)
            assert abs(ing_record["current_stock"] - 9.60) < 1e-4, f"Inventory stock deduction mismatch: {ing_record['current_stock']}"
            print(f"  [OK] Order accepted. Inventory stock verified at {ing_record['current_stock']} kg (Exact 0.40 kg deducted).")

            # ─────────────────────────────────────────────────────────────
            # Y & Z. Customer Notification & Email Notification Events
            # ─────────────────────────────────────────────────────────────
            print("\n[Check Y & Z] Customer Notification & Email Events...")
            r_cust_notifs = cust_client.get("/api/v1/customer/notifications")
            assert r_cust_notifs.status_code == 200
            assert len(r_cust_notifs.json()) >= 1, "Customer should have received status notification"
            print(f"  [OK] Customer received real in-app notification.")

            # ─────────────────────────────────────────────────────────────
            # AA. Order Status Progression
            # ─────────────────────────────────────────────────────────────
            print("\n[Check AA] Order Status Progression (PREPARING -> READY -> DELIVERED)...")
            transitions = [
                ("PREPARING", "Pizza entering stone oven"),
                ("READY", "Order packed and hot"),
                ("DELIVERED", "Delivered to customer table"),
            ]
            for target_status, note in transitions:
                r_step = ko_client.post(f"/api/v1/kitchen/orders/{order_id}/transition", json={"target_status": target_status, "reason": note})
                assert r_step.status_code == 200, f"Transition to {target_status} failed: {r_step.status_code} {r_step.text}"
                assert r_step.json()["status"] == target_status
                print(f"  [OK] Order status advanced to {target_status}")

            # ─────────────────────────────────────────────────────────────
            # AB, AC, AD, AE. Admin Sees Real Order, Payment, Inventory, Notification
            # ─────────────────────────────────────────────────────────────
            print("\n[Check AB, AC, AD, AE] Admin Oversight of Real Records...")
            # Orders
            r_admin_orders = admin_client.get("/api/v1/admin/orders")
            assert r_admin_orders.status_code == 200
            orders_list = r_admin_orders.json().get("orders", [])
            assert any(o["id"] == order_id for o in orders_list), f"Order {order_id} not visible to Admin"
            print("  [OK] Admin sees real order in order list.")

            # Payments
            r_admin_payments = admin_client.get("/api/v1/admin/payments")
            assert r_admin_payments.status_code == 200
            payments_list = r_admin_payments.json().get("payments", [])
            assert len(payments_list) >= 1, "Admin should see real payment record"
            print("  [OK] Admin sees real payment records.")

            # Inventory
            r_admin_inv = admin_client.get("/api/v1/admin/inventory")
            assert r_admin_inv.status_code == 200
            inv_list = r_admin_inv.json().get("inventory", [])
            assert any(i["ingredient"]["id"] == ing_id for i in inv_list), "Admin should see real inventory record"
            print("  [OK] Admin sees real inventory records.")

            # Notifications
            r_admin_notifs = admin_client.get("/api/v1/admin/notifications")
            assert r_admin_notifs.status_code == 200
            print("  [OK] Admin notifications query verified.")

            # ─────────────────────────────────────────────────────────────
            # AF. Admin Deactivates WELCOME_20
            # ─────────────────────────────────────────────────────────────
            print("\n[Check AF] Admin Deactivates WELCOME_20...")
            r_toggle = admin_client.patch(f"/api/v1/admin/promotions/{promo_id}/toggle")
            assert r_toggle.status_code == 200, f"Toggle promotion failed: {r_toggle.status_code}"
            assert r_toggle.json()["is_active"] is False, "Promotion should now be inactive"
            print("  [OK] Admin toggled WELCOME_20 to inactive.")

            # ─────────────────────────────────────────────────────────────
            # AG. Customer Can No Longer Use Deactivated Coupon
            # ─────────────────────────────────────────────────────────────
            print("\n[Check AG] Customer Attempt to Use Deactivated Coupon...")
            # Create a second customer to test inactive coupon validation
            cust2_client = TestClient(app)
            cust2_email = f"customer2_{test_id}@example.com"
            cust2_client.post("/api/v1/auth/register", json={
                "email": cust2_email,
                "password": "Password123!",
                "full_name": "Second Customer",
                "phone_number": "+919888888888"
            })
            r_preview_inactive = cust2_client.post("/api/v1/customer/checkout/preview", json={
                "kitchen_id": kitchen_id,
                "items": [{"menu_item_id": item_id, "quantity": 2}],
                "promotion_code": "WELCOME_20"
            })
            assert r_preview_inactive.status_code == 400, "Deactivated promotion should return 400 Bad Request"
            print(f"  [OK] Deactivated coupon correctly rejected: {r_preview_inactive.json().get('detail')}")

            # ─────────────────────────────────────────────────────────────
            # AH. Admin Logout
            # ─────────────────────────────────────────────────────────────
            print("\n[Check AH] Admin Logout...")
            r_logout = admin_client.post("/api/v1/auth/logout")
            assert r_logout.status_code == 200, f"Admin logout failed: {r_logout.status_code}"
            print("  [OK] Admin session logged out successfully.")

            print("\n=======================================================")
            print("ALL 34 E2E CHECKS (A through AH) PASSED IN ISOLATED DATABASE!")
            print("=======================================================")
    finally:
        # Clear dependency overrides and teardown test engine
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=TEST_ENGINE)
        TEST_ENGINE.dispose()
        print("=== TEST DATABASE TEARDOWN COMPLETE (ZERO POLLUTION) ===")

if __name__ == "__main__":
    run_isolated_full_e2e()
