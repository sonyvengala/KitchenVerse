"""
Live E2E Verification Script for Admin-Assisted Order Cancellation.
Tests against the live running backend at http://localhost:8000 with real database persistence.
Tests:
  1. Live Approval Flow
  2. Live Rejection Flow
  3. Clean up only synthetic test records
"""
import httpx
import uuid
import sys
import os
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, r"C:\CloudKitchen")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
from datetime import datetime, timezone

from backend.app.core.database import SessionLocal
from backend.app.core.security import get_password_hash
from backend.app.models.user import User, KitchenProfile, Address
from backend.app.models.enums import UserRole, OrderStatus, PaymentStatus, InventoryTransactionType
from backend.app.models.menu import MenuItem, Ingredient, MenuItemIngredient
from backend.app.models.order import Order, OrderItem, CancellationRequest
from backend.app.models.inventory import WasteRecord, InventoryTransaction, Purchase, Inventory
from backend.app.models.platform import Notification

BASE_URL = "http://localhost:8000"


def main():
    print("=" * 60)
    print("STARTING LIVE E2E VERIFICATION (http://localhost:8000)")
    print("=" * 60)

    db = SessionLocal()
    synthetic_user_ids = []
    synthetic_order_ids = []

    try:
        # 1. Setup isolated synthetic users & kitchen
        tag = uuid.uuid4().hex[:6]
        admin_email = f"synth_admin_{tag}@example.com"
        ko_email = f"synth_chef_{tag}@example.com"
        cust_email = f"synth_cust_{tag}@example.com"
        password = "SecurePass123!"
        hashed_pw = get_password_hash(password)

        admin = User(
            email=admin_email,
            hashed_password=hashed_pw,
            full_name=f"Synth Admin {tag}",
            role=UserRole.ADMIN,
            is_active=True,
            is_verified=True,
        )
        ko = User(
            email=ko_email,
            hashed_password=hashed_pw,
            full_name=f"Synth Chef {tag}",
            role=UserRole.KITCHEN_OWNER,
            is_active=True,
            is_verified=True,
        )
        cust = User(
            email=cust_email,
            hashed_password=hashed_pw,
            full_name=f"Synth Customer {tag}",
            role=UserRole.CUSTOMER,
            is_active=True,
            is_verified=True,
        )
        db.add_all([admin, ko, cust])
        db.commit()
        synthetic_user_ids.extend([admin.id, ko.id, cust.id])

        kitchen = KitchenProfile(
            user_id=ko.id,
            kitchen_name=f"Live Test Kitchen {tag}",
            address="123 MG Road",
            city="Bangalore",
            phone="+919876543210",
            is_open=True,
            is_approved=True,
            approval_status="APPROVED",
        )
        db.add(kitchen)
        db.commit()

        # Ingredients & Recipe
        # 1 Biryani requires: 0.20 kg rice, 0.18 kg chicken, 0.02 L oil
        rice = Ingredient(kitchen_id=kitchen.id, name=f"Rice_{tag}", unit="kg", current_stock=20.0, minimum_stock_threshold=2.0)
        chicken = Ingredient(kitchen_id=kitchen.id, name=f"Chicken_{tag}", unit="kg", current_stock=20.0, minimum_stock_threshold=2.0)
        oil = Ingredient(kitchen_id=kitchen.id, name=f"Oil_{tag}", unit="L", current_stock=20.0, minimum_stock_threshold=2.0)
        db.add_all([rice, chicken, oil])
        db.commit()

        p1 = Purchase(kitchen_id=kitchen.id, ingredient_id=rice.id, supplier_name="Metro", unit="kg", quantity=10.0, unit_cost=50.0, total_cost=500.0)
        p2 = Purchase(kitchen_id=kitchen.id, ingredient_id=chicken.id, supplier_name="Fresh Farm", unit="kg", quantity=10.0, unit_cost=180.0, total_cost=1800.0)
        p3 = Purchase(kitchen_id=kitchen.id, ingredient_id=oil.id, supplier_name="Fortune", unit="L", quantity=10.0, unit_cost=120.0, total_cost=1200.0)
        db.add_all([p1, p2, p3])
        db.commit()

        dish = MenuItem(
            kitchen_id=kitchen.id,
            name=f"Live Dum Biryani {tag}",
            category="Biryani",
            cuisine="Mughlai",
            price=250.0,
            is_available=True,
        )
        db.add(dish)
        db.commit()

        db.add(MenuItemIngredient(menu_item_id=dish.id, ingredient_id=rice.id, quantity_required=0.20))
        db.add(MenuItemIngredient(menu_item_id=dish.id, ingredient_id=chicken.id, quantity_required=0.18))
        db.add(MenuItemIngredient(menu_item_id=dish.id, ingredient_id=oil.id, quantity_required=0.02))
        db.commit()

        # ─────────────────────────────────────────────────────────────
        # PART 1: LIVE APPROVAL FLOW
        # ─────────────────────────────────────────────────────────────
        print("\n--- TEST FLOW 1: ADMIN APPROVAL ---")

        # Create READY order: 2 Biryanis
        order1 = Order(
            order_number=f"LIVE-APP-{tag}",
            customer_id=cust.id,
            kitchen_id=kitchen.id,
            status=OrderStatus.READY,
            subtotal=500.0,
            tax=25.0,
            delivery_fee=30.0,
            total_amount=555.0,
            payment_status=PaymentStatus.SUCCESS,
            delivery_address_text="Whitefield, Bangalore",
        )
        db.add(order1)
        db.commit()
        synthetic_order_ids.append(order1.id)

        item1 = OrderItem(
            order_id=order1.id,
            menu_item_id=dish.id,
            item_name=dish.name,
            unit_price=250.0,
            quantity=2,
            subtotal=500.0,
        )
        db.add(item1)
        db.commit()

        # Step 1: Customer logs in via HTTP
        cust_session = httpx.Client()
        res_login = cust_session.post(f"{BASE_URL}/api/v1/auth/login", json={"email": cust_email, "password": password})
        assert res_login.status_code == 200, f"Customer login failed: {res_login.text}"
        print("✓ Customer logged in successfully via API")

        # Step 2: Customer attempts direct cancel -> MUST FAIL (400)
        res_direct = cust_session.post(f"{BASE_URL}/api/v1/customer/orders/{order1.id}/cancel?reason=Changed+mind")
        assert res_direct.status_code == 400, f"Expected direct cancel to fail with 400, got {res_direct.status_code}: {res_direct.text}"
        print("✓ Server-side protection verified: Direct customer cancellation of READY order was blocked (HTTP 400)")

        # Step 3: Customer requests cancellation
        res_req = cust_session.post(
            f"{BASE_URL}/api/v1/customer/orders/{order1.id}/cancellation-request",
            json={"reason": "Cannot receive the order", "customer_note": "Guest cancelled visit"},
        )
        assert res_req.status_code == 200, f"Customer request failed: {res_req.text}"
        req_data = res_req.json()
        assert req_data["status"] == "PENDING"
        cr1_id = req_data["id"]
        print(f"✓ Cancellation request created: ID={cr1_id}, status={req_data['status']}")

        # Step 4: Verify order is still READY
        db.refresh(order1)
        assert order1.status == OrderStatus.READY, f"Order status should remain READY, got {order1.status}"
        print("✓ Order remains in READY status pending admin decision")

        # Step 5: Admin logs in via HTTP
        admin_session = httpx.Client()
        res_adm_login = admin_session.post(f"{BASE_URL}/api/v1/auth/login", json={"email": admin_email, "password": password})
        assert res_adm_login.status_code == 200, f"Admin login failed: {res_adm_login.text}"
        print("✓ Admin logged in successfully via API")

        # Step 6: Admin lists cancellation requests
        res_cr_list = admin_session.get(f"{BASE_URL}/api/v1/admin/cancellation-requests?status=PENDING")
        assert res_cr_list.status_code == 200
        pending_list = res_cr_list.json()
        assert any(r["id"] == cr1_id for r in pending_list), "Pending request not found in admin list"
        print(f"✓ Admin retrieved pending requests: found request {cr1_id}")

        # Step 7: Admin approves the request
        res_approve = admin_session.post(
            f"{BASE_URL}/api/v1/admin/cancellation-requests/{cr1_id}/approve",
            json={"admin_note": "Approved by Duty Manager"},
        )
        assert res_approve.status_code == 200, f"Admin approval failed: {res_approve.text}"
        app_json = res_approve.json()
        assert app_json["decision"] == "APPROVED"
        assert app_json["order_status"] == "CANCELLED"
        print("✓ Admin approved request successfully: decision=APPROVED, order_status=CANCELLED")

        # Step 8: Verify database state
        db.refresh(order1)
        assert order1.status == OrderStatus.CANCELLED
        print(f"✓ Order {order1.order_number} state verified in DB: CANCELLED")

        cr1 = db.query(CancellationRequest).filter(CancellationRequest.id == cr1_id).first()
        assert cr1.status == "APPROVED"
        assert cr1.admin_id == admin.id
        print("✓ CancellationRequest state verified in DB: APPROVED")

        # Step 9: Verify wastage records
        # 2 Biryanis -> 2 * 0.20 = 0.40 kg rice, 2 * 0.18 = 0.36 kg chicken, 2 * 0.02 = 0.04 L oil
        w_records = db.query(WasteRecord).filter(WasteRecord.order_id == order1.id).all()
        assert len(w_records) >= 3, f"Expected 3 wastage records, got {len(w_records)}"
        w_rice = next(w for w in w_records if w.ingredient_id == rice.id)
        w_chicken = next(w for w in w_records if w.ingredient_id == chicken.id)
        w_oil = next(w for w in w_records if w.ingredient_id == oil.id)
        assert round(float(w_rice.quantity), 2) == 0.40
        assert round(float(w_chicken.quantity), 2) == 0.36
        assert round(float(w_oil.quantity), 2) == 0.04
        assert w_rice.reason == "Customer Cancellation — Admin Approved"
        print(f"✓ Recipe-driven wastage verified: Rice={w_rice.quantity} kg, Chicken={w_chicken.quantity} kg, Oil={w_oil.quantity} L")

        # Step 10: Verify inventory transactions
        w_txns = db.query(InventoryTransaction).filter(
            InventoryTransaction.reference_order_id == order1.id,
            InventoryTransaction.transaction_type == InventoryTransactionType.WASTE,
        ).all()
        assert len(w_txns) >= 3, f"Expected 3 WASTE inventory ledger entries, got {len(w_txns)}"
        print(f"✓ Inventory ledger entries verified: {len(w_txns)} WASTE transactions recorded")

        # Step 11: Verify notifications
        cust_notif = db.query(Notification).filter(
            Notification.user_id == cust.id,
            Notification.event_type == "ORDER_CANCELLED",
        ).first()
        assert cust_notif is not None
        assert "approved" in cust_notif.message.lower()
        print(f"✓ Customer notification verified: '{cust_notif.title}' - '{cust_notif.message}'")

        ko_notif = db.query(Notification).filter(
            Notification.user_id == ko.id,
            Notification.event_type == "ORDER_CANCELLED",
        ).first()
        assert ko_notif is not None
        print(f"✓ Kitchen Owner notification verified: '{ko_notif.title}'")

        # ─────────────────────────────────────────────────────────────
        # PART 2: LIVE REJECTION FLOW
        # ─────────────────────────────────────────────────────────────
        print("\n--- TEST FLOW 2: ADMIN REJECTION ---")

        # Create second READY order: 1 Biryani
        order2 = Order(
            order_number=f"LIVE-REJ-{tag}",
            customer_id=cust.id,
            kitchen_id=kitchen.id,
            status=OrderStatus.READY,
            subtotal=250.0,
            tax=12.5,
            delivery_fee=30.0,
            total_amount=292.5,
            payment_status=PaymentStatus.SUCCESS,
            delivery_address_text="Indiranagar, Bangalore",
        )
        db.add(order2)
        db.commit()
        synthetic_order_ids.append(order2.id)

        item2 = OrderItem(
            order_id=order2.id,
            menu_item_id=dish.id,
            item_name=dish.name,
            unit_price=250.0,
            quantity=1,
            subtotal=250.0,
        )
        db.add(item2)
        db.commit()

        # Step 1: Customer requests cancellation
        res_req2 = cust_session.post(
            f"{BASE_URL}/api/v1/customer/orders/{order2.id}/cancellation-request",
            json={"reason": "Ordered by mistake"},
        )
        assert res_req2.status_code == 200
        cr2_id = res_req2.json()["id"]
        print(f"✓ Second cancellation request created: ID={cr2_id}")

        # Step 2: Admin tries to reject without reason -> MUST FAIL (400)
        res_bad_rej = admin_session.post(
            f"{BASE_URL}/api/v1/admin/cancellation-requests/{cr2_id}/reject",
            json={"admin_note": ""},
        )
        assert res_bad_rej.status_code == 400
        print("✓ Rejection without note was correctly rejected (HTTP 400: Rejection reason required)")

        # Step 3: Admin rejects with real reason
        rej_reason = "Order is already packed and assigned to delivery partner."
        res_rej = admin_session.post(
            f"{BASE_URL}/api/v1/admin/cancellation-requests/{cr2_id}/reject",
            json={"admin_note": rej_reason},
        )
        assert res_rej.status_code == 200
        rej_json = res_rej.json()
        assert rej_json["decision"] == "REJECTED"
        assert rej_json["order_status"] == "READY"
        print(f"✓ Admin rejected request successfully: decision=REJECTED, order_status=READY")

        # Step 4: Verify order remains READY in DB
        db.refresh(order2)
        assert order2.status == OrderStatus.READY, f"Order status should remain READY, got {order2.status}"
        print(f"✓ Order {order2.order_number} state verified in DB: READY")

        cr2 = db.query(CancellationRequest).filter(CancellationRequest.id == cr2_id).first()
        assert cr2.status == "REJECTED"
        assert cr2.admin_note == rej_reason
        print("✓ CancellationRequest state verified in DB: REJECTED with admin_note saved")

        # Step 5: Verify NO wastage was created for order2
        w2_count = db.query(WasteRecord).filter(WasteRecord.order_id == order2.id).count()
        assert w2_count == 0, f"Expected 0 wastage records for rejected order, got {w2_count}"
        print("✓ Verified ZERO wastage records created for rejected order")

        # Step 6: Verify NO WASTE inventory ledger entries
        w2_txns = db.query(InventoryTransaction).filter(
            InventoryTransaction.reference_order_id == order2.id,
            InventoryTransaction.transaction_type == InventoryTransactionType.WASTE,
        ).count()
        assert w2_txns == 0, f"Expected 0 WASTE inventory transactions, got {w2_txns}"
        print("✓ Verified ZERO WASTE inventory transactions created for rejected order")

        # Step 7: Verify customer received rejection notification
        rej_notif = db.query(Notification).filter(
            Notification.user_id == cust.id,
            Notification.event_type == "CANCELLATION_REJECTED",
        ).first()
        assert rej_notif is not None
        assert rej_reason in rej_notif.message
        print(f"✓ Customer rejection notification verified: contains admin reason '{rej_reason}'")

        # Step 8: Customer order tracking view returns rejection details
        res_track = cust_session.get(f"{BASE_URL}/api/v1/customer/orders/{order2.id}")
        assert res_track.status_code == 200
        order_detail = res_track.json()
        assert order_detail["status"] == "READY"
        assert order_detail["cancellation_request"] is not None
        assert order_detail["cancellation_request"]["status"] == "REJECTED"
        assert order_detail["cancellation_request"]["admin_note"] == rej_reason
        print("✓ Customer Order Details API returns cancellation_request with status=REJECTED and admin_note")

        print("\n" + "=" * 60)
        print("ALL LIVE E2E APPROVAL & REJECTION TESTS PASSED WITH 100% SUCCESS!")
        print("=" * 60)

    finally:
        # Clean up ONLY synthetic test data
        print("\nCleaning up isolated synthetic test data...")
        try:
            for oid in synthetic_order_ids:
                db.query(WasteRecord).filter(WasteRecord.order_id == oid).delete(synchronize_session=False)
                db.query(InventoryTransaction).filter(InventoryTransaction.reference_order_id == oid).delete(synchronize_session=False)
                db.query(CancellationRequest).filter(CancellationRequest.order_id == oid).delete(synchronize_session=False)
                db.query(OrderItem).filter(OrderItem.order_id == oid).delete(synchronize_session=False)
                db.query(Order).filter(Order.id == oid).delete(synchronize_session=False)

            for uid in synthetic_user_ids:
                db.query(Notification).filter(Notification.user_id == uid).delete(synchronize_session=False)
                db.query(MenuItemIngredient).filter(MenuItemIngredient.menu_item.has(kitchen_id=kitchen.id)).delete(synchronize_session=False)
                db.query(MenuItem).filter(MenuItem.kitchen_id == kitchen.id).delete(synchronize_session=False)
                db.query(Purchase).filter(Purchase.kitchen_id == kitchen.id).delete(synchronize_session=False)
                db.query(Ingredient).filter(Ingredient.kitchen_id == kitchen.id).delete(synchronize_session=False)
                db.query(KitchenProfile).filter(KitchenProfile.user_id == uid).delete(synchronize_session=False)
                db.query(User).filter(User.id == uid).delete(synchronize_session=False)

            db.commit()
            print("✓ Synthetic test data cleaned up successfully.")
        except Exception as e:
            db.rollback()
            print(f"Warning during cleanup: {e}")
        finally:
            db.close()


if __name__ == "__main__":
    main()
