"""
Test suite validating CloudKitchen's Customer Order Email Lifecycle Requirements:
Requirement: Customers should receive only TWO emails per order:
  1. Order Placed: Exactly one confirmation email after the order is successfully created and saved.
  2. Order Successful: Exactly one final success email only when the order status changes to DELIVERED.

Stop sending customer emails for these intermediate statuses:
  - ACCEPTED (KITCHEN_ACCEPTED)
  - PREPARING
  - READY
  - OUT_FOR_DELIVERY
  - Any other intermediate order status

Deduplication / Idempotency:
  - No duplicate emails from repeated API requests, repeated status updates, or retries.
  - Kitchen-owner notifications and admin notifications remain functional.
"""

from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.security import get_password_hash
from backend.app.models.enums import UserRole, OrderStatus, PaymentStatus
from backend.app.models.user import User, KitchenProfile, CustomerProfile, Address
from backend.app.models.menu import MenuItem, Ingredient, MenuItemIngredient
from backend.app.models.inventory import Inventory
from backend.app.models.order import Order, OrderItem
from backend.app.core.email import email_service
from backend.app.services.kitchen_service import KitchenService
from backend.app.services.customer_service import CustomerService


def _create_user(db: Session, email: str, full_name: str, role: UserRole) -> User:
    user = User(
        email=email,
        hashed_password=get_password_hash("TestPass123!"),
        full_name=full_name,
        role=role,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.flush()
    return user


def _create_kitchen(db: Session, owner: User, name: str = "Tandoor Nights") -> KitchenProfile:
    kitchen = KitchenProfile(
        user_id=owner.id,
        kitchen_name=name,
        address="100 Baker Street",
        city="Mumbai",
        is_open=True,
        is_approved=True,
        rating=4.8,
        rating_count=50,
    )
    db.add(kitchen)
    db.flush()
    return kitchen


def _create_menu_with_stock(db: Session, kitchen_id: str):
    ing = Ingredient(
        kitchen_id=kitchen_id,
        name="Paneer",
        unit="kg",
        current_stock=50.0,
        minimum_stock_threshold=5.0,
        reorder_quantity=20.0,
    )
    db.add(ing)
    db.flush()

    inv = Inventory(kitchen_id=kitchen_id, ingredient_id=ing.id, quantity=50.0, unit="kg")
    db.add(inv)

    item = MenuItem(
        kitchen_id=kitchen_id,
        name="Paneer Tikka",
        category="Starters",
        cuisine="North Indian",
        price=250.0,
        is_available=True,
    )
    db.add(item)
    db.flush()

    link = MenuItemIngredient(menu_item_id=item.id, ingredient_id=ing.id, quantity_required=0.25)
    db.add(link)
    db.commit()
    return item


def _login(client: TestClient, email: str):
    client.post("/api/v1/auth/login", json={"email": email, "password": "TestPass123!"})


def test_customer_receives_exactly_two_emails_across_full_order_lifecycle(client: TestClient, db_session: Session):
    """
    Test end-to-end order flow from creation to delivery:
    1. Order creation -> 1 Order Placed email to customer (+ 1 alert to kitchen owner)
    2. ACCEPTED (KITCHEN_ACCEPTED) -> 0 customer email
    3. PREPARING -> 0 customer email
    4. READY -> 0 customer email
    5. OUT_FOR_DELIVERY -> 0 customer email
    6. DELIVERED -> 1 Order Delivered email to customer
    Total customer emails for the completed order: EXACTLY 2.
    """
    owner = _create_user(db_session, "chef.lifecycle@test.com", "Chef Kumar", UserRole.KITCHEN_OWNER)
    kitchen = _create_kitchen(db_session, owner, "Royal Flavors")
    cust_user = _create_user(db_session, "customer.lifecycle@test.com", "Anita Sharma", UserRole.CUSTOMER)
    
    addr = Address(
        user_id=cust_user.id,
        address_line1="Flat 402, Sunshine Apts",
        city="Mumbai",
        state="Maharashtra",
        postal_code="400001",
        is_default=True,
    )
    db_session.add(addr)
    db_session.commit()

    menu_item = _create_menu_with_stock(db_session, kitchen.id)

    with patch.object(email_service, "_send_sync", return_value={"status": "sent"}) as mock_send:
        # Step 1: Customer creates and places the order
        _login(client, cust_user.email)
        create_payload = {
            "kitchen_id": kitchen.id,
            "delivery_address_id": addr.id,
            "payment_method": "COD",
            "items": [{"menu_item_id": menu_item.id, "quantity": 2}],
            "special_instructions": "Make it spicy",
        }
        res = client.post("/api/v1/customer/orders", json=create_payload)
        assert res.status_code in [200, 201], res.text
        order_data = res.json()
        order_id = order_data["id"]
        order_number = order_data["order_number"]

        # Assert step 1 email dispatches:
        # Customer should receive 1 "Order Placed" email
        # Kitchen owner receives 1 new order alert
        assert mock_send.call_count == 2
        customer_emails = [c for c in mock_send.call_args_list if c[0][0] == cust_user.email]
        kitchen_emails = [c for c in mock_send.call_args_list if c[0][0] == owner.email]
        assert len(customer_emails) == 1
        assert len(kitchen_emails) == 1
        assert "Order Placed" in customer_emails[0][0][1]

        mock_send.reset_mock()

        # Step 2: Kitchen accepts the order (ACCEPTED / KITCHEN_ACCEPTED)
        _login(client, owner.email)
        res_accept = client.post(f"/api/v1/kitchen/orders/{order_id}/accept")
        assert res_accept.status_code == 200
        assert res_accept.json()["status"] == "KITCHEN_ACCEPTED"

        # Customer must NOT receive email for ACCEPTED
        assert mock_send.call_count == 0

        # Step 3: Kitchen transitions status to PREPARING
        res_prep = client.post(f"/api/v1/kitchen/orders/{order_id}/transition", json={"target_status": "PREPARING"})
        assert res_prep.status_code == 200
        assert res_prep.json()["status"] == "PREPARING"

        # Customer must NOT receive email for PREPARING
        assert mock_send.call_count == 0

        # Step 4: Kitchen transitions status to READY
        res_ready = client.post(f"/api/v1/kitchen/orders/{order_id}/transition", json={"target_status": "READY"})
        assert res_ready.status_code == 200
        assert res_ready.json()["status"] == "READY"

        # Customer must NOT receive email for READY
        assert mock_send.call_count == 0

        # Step 5: Kitchen transitions status to OUT_FOR_DELIVERY
        res_out = client.post(f"/api/v1/kitchen/orders/{order_id}/transition", json={"target_status": "OUT_FOR_DELIVERY"})
        assert res_out.status_code == 200
        assert res_out.json()["status"] == "OUT_FOR_DELIVERY"

        # Customer must NOT receive email for OUT_FOR_DELIVERY
        assert mock_send.call_count == 0

        # Step 6: Order transitioned to DELIVERED (Order Successful)
        res_deliv = client.post(f"/api/v1/kitchen/orders/{order_id}/transition", json={"target_status": "DELIVERED"})
        assert res_deliv.status_code == 200
        assert res_deliv.json()["status"] == "DELIVERED"

        # Customer must receive exactly 1 email for DELIVERED
        assert mock_send.call_count == 1
        deliv_call = mock_send.call_args_list[0]
        assert deliv_call[0][0] == cust_user.email
        assert f"Order Delivered Successfully #{order_number}" in deliv_call[0][1]


def test_repeated_delivered_transition_does_not_send_duplicate_customer_email(client: TestClient, db_session: Session):
    """
    Test idempotency: If transition is attempted again or repeated,
    it should not send duplicate DELIVERED emails to customer.
    """
    owner = _create_user(db_session, "chef.repeat@test.com", "Chef Repeat", UserRole.KITCHEN_OWNER)
    kitchen = _create_kitchen(db_session, owner, "Repeat Bites")
    cust_user = _create_user(db_session, "customer.repeat@test.com", "Rohit Roy", UserRole.CUSTOMER)
    db_session.commit()

    order = Order(
        order_number="ORD-REPEAT-001",
        customer_id=cust_user.id,
        kitchen_id=kitchen.id,
        status=OrderStatus.READY,
        subtotal=200.0,
        tax=10.0,
        delivery_fee=30.0,
        discount_amount=0.0,
        total_amount=240.0,
        payment_status=PaymentStatus.SUCCESS,
    )
    db_session.add(order)
    db_session.commit()

    with patch.object(email_service, "_send_sync", return_value={"status": "sent"}) as mock_send:
        # First transition to DELIVERED
        KitchenService.transition_order_status(db_session, owner, order.id, OrderStatus.DELIVERED)
        assert mock_send.call_count == 1
        assert mock_send.call_args_list[0][0][0] == cust_user.email

        mock_send.reset_mock()

        # Repeated transition attempt from DELIVERED to DELIVERED should raise 422 and dispatch 0 emails
        with pytest.raises(Exception):
            KitchenService.transition_order_status(db_session, owner, order.id, OrderStatus.DELIVERED)

        assert mock_send.call_count == 0


def test_intermediate_statuses_generate_no_customer_emails(client: TestClient, db_session: Session):
    """
    Directly verify that transitions through intermediate statuses generate zero customer emails.
    """
    owner = _create_user(db_session, "chef.intermediate@test.com", "Chef Inter", UserRole.KITCHEN_OWNER)
    kitchen = _create_kitchen(db_session, owner, "Inter Bistro")
    cust_user = _create_user(db_session, "customer.inter@test.com", "Meera Sen", UserRole.CUSTOMER)
    db_session.commit()

    order = Order(
        order_number="ORD-INTER-001",
        customer_id=cust_user.id,
        kitchen_id=kitchen.id,
        status=OrderStatus.KITCHEN_ACCEPTED,
        subtotal=150.0,
        tax=7.5,
        delivery_fee=25.0,
        discount_amount=0.0,
        total_amount=182.5,
        payment_status=PaymentStatus.SUCCESS,
    )
    db_session.add(order)
    db_session.commit()

    with patch.object(email_service, "_send_sync", return_value={"status": "sent"}) as mock_send:
        # KITCHEN_ACCEPTED -> PREPARING
        KitchenService.transition_order_status(db_session, owner, order.id, OrderStatus.PREPARING)
        assert mock_send.call_count == 0

        # PREPARING -> READY
        KitchenService.transition_order_status(db_session, owner, order.id, OrderStatus.READY)
        assert mock_send.call_count == 0

        # READY -> OUT_FOR_DELIVERY
        KitchenService.transition_order_status(db_session, owner, order.id, OrderStatus.OUT_FOR_DELIVERY)
        assert mock_send.call_count == 0

        # Total emails dispatched during intermediate phases: strictly ZERO
        assert mock_send.call_count == 0
