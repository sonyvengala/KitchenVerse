"""
End-to-End Real-Time Cross-Role Updates & Independent Sessions Test Suite.
KitchenVerse Platform.
"""
import pytest
from fastapi.testclient import TestClient
import uuid
import time
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.core.database import SessionLocal
from backend.app.models.user import User, KitchenProfile, CustomerProfile, Address
from backend.app.models.menu import MenuItem, Ingredient, MenuItemIngredient
from backend.app.models.enums import UserRole, OrderStatus, PaymentStatus
from backend.app.core.security import get_password_hash
from backend.app.core.session import create_user_session, get_active_session, revoke_session
from backend.app.websockets.connection_manager import ws_manager

@pytest.fixture
def test_setup(db_session: Session):
    unique_suffix = str(uuid.uuid4())[:8]

    # 1. Admin
    admin = User(
        id=f"admin_{unique_suffix}",
        email=f"admin_{unique_suffix}@cloudkitchen.com",
        hashed_password=get_password_hash("AdminPass123!"),
        full_name="Platform Admin",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    db_session.add(admin)

    # 2. Kitchen Owner & Profile
    ko_user = User(
        id=f"ko_{unique_suffix}",
        email=f"ko_{unique_suffix}@cloudkitchen.com",
        hashed_password=get_password_hash("KitchenPass123!"),
        full_name="Master Chef",
        role=UserRole.KITCHEN_OWNER,
        is_active=True,
        is_verified=True,
    )
    db_session.add(ko_user)
    db_session.flush()

    kitchen = KitchenProfile(
        id=f"kitchen_{unique_suffix}",
        user_id=ko_user.id,
        kitchen_name=f"Chef Delight {unique_suffix}",
        address="100 Food Street",
        city="Bengaluru",
        state="Karnataka",
        is_open=True,
        is_approved=True,
        approval_status="APPROVED",
    )
    db_session.add(kitchen)
    db_session.flush()

    # Ingredient and Menu Item
    ingredient = Ingredient(
        id=f"ing_{unique_suffix}",
        kitchen_id=kitchen.id,
        name="Basmati Rice",
        unit="kg",
        current_stock=50.0,
        minimum_stock_threshold=5.0,
    )
    db_session.add(ingredient)
    db_session.flush()

    menu_item = MenuItem(
        id=f"item_{unique_suffix}",
        kitchen_id=kitchen.id,
        meal_id=999,
        name="Royal Biryani",
        category="Rice Bowl",
        cuisine="Indian",
        price=350.0,
        is_available=True,
        is_veg=True,
    )
    db_session.add(menu_item)
    db_session.flush()

    db_session.add(MenuItemIngredient(
        menu_item_id=menu_item.id,
        ingredient_id=ingredient.id,
        quantity_required=0.5,
    ))

    # 3. Customer & Address
    cust_user = User(
        id=f"cust_{unique_suffix}",
        email=f"cust_{unique_suffix}@gmail.com",
        hashed_password=get_password_hash("CustPass123!"),
        full_name="Loyal Customer",
        role=UserRole.CUSTOMER,
        is_active=True,
        is_verified=True,
    )
    db_session.add(cust_user)
    db_session.flush()

    address = Address(
        id=f"addr_{unique_suffix}",
        user_id=cust_user.id,
        address_line1="42 Galaxy Apts",
        city="Bengaluru",
        state="Karnataka",
        postal_code="560001",
        is_default=True,
    )
    db_session.add(address)

    db_session.commit()

    yield {
        "admin": admin,
        "ko_user": ko_user,
        "kitchen": kitchen,
        "cust_user": cust_user,
        "address": address,
        "menu_item": menu_item,
        "ingredient": ingredient,
    }

    # Isolated fixture teardown: clean up all created records
    try:
        from backend.app.models.order import Order, OrderItem, Payment
        orders = db_session.query(Order).filter(Order.kitchen_id == kitchen.id).all()
        for o in orders:
            db_session.query(OrderItem).filter(OrderItem.order_id == o.id).delete()
            db_session.query(Payment).filter(Payment.order_id == o.id).delete()
            db_session.delete(o)
        db_session.query(MenuItemIngredient).filter(MenuItemIngredient.menu_item_id == menu_item.id).delete()
        db_session.query(MenuItem).filter(MenuItem.id == menu_item.id).delete()
        db_session.query(Ingredient).filter(Ingredient.id == ingredient.id).delete()
        db_session.query(KitchenProfile).filter(KitchenProfile.id == kitchen.id).delete()
        db_session.query(Address).filter(Address.id == address.id).delete()
        db_session.query(User).filter(User.id.in_([admin.id, ko_user.id, cust_user.id])).delete()
        db_session.commit()
    except Exception:
        db_session.rollback()



def test_independent_sessions_concurrency(client: TestClient, db_session: Session, test_setup):
    """
    Ensure Admin, Kitchen Owner, and Customer maintain independent sessions.
    Revoking/logging out one session must NOT invalidate the others.
    """
    admin = test_setup["admin"]
    ko_user = test_setup["ko_user"]
    cust = test_setup["cust_user"]

    # Create concurrent sessions (simulating separate browser profiles)
    admin_session = create_user_session(db_session, admin.id)
    ko_session = create_user_session(db_session, ko_user.id)
    cust_session = create_user_session(db_session, cust.id)

    assert admin_session.session_id != ko_session.session_id != cust_session.session_id

    # Verify all 3 sessions are active and return proper roles
    res_admin = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {admin_session.session_id}"})
    assert res_admin.status_code == 200
    assert res_admin.json()["role"] == "ADMIN"

    res_ko = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {ko_session.session_id}"})
    assert res_ko.status_code == 200
    assert res_ko.json()["role"] == "KITCHEN_OWNER"

    res_cust = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {cust_session.session_id}"})
    assert res_cust.status_code == 200
    assert res_cust.json()["role"] == "CUSTOMER"

    # Revoke Kitchen Owner's session (simulating logout in Kitchen tab/profile)
    revoke_session(db_session, ko_session.session_id)

    # Kitchen Owner should now be 401 Unauthorized
    res_ko_after = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {ko_session.session_id}"})
    assert res_ko_after.status_code == 401

    # Admin and Customer sessions MUST remain fully active and valid!
    res_admin_after = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {admin_session.session_id}"})
    assert res_admin_after.status_code == 200
    assert res_admin_after.json()["role"] == "ADMIN"

    res_cust_after = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {cust_session.session_id}"})
    assert res_cust_after.status_code == 200
    assert res_cust_after.json()["role"] == "CUSTOMER"


def test_websocket_authentication_and_handshake(client: TestClient, db_session: Session, test_setup):
    """
    Test WebSocket endpoint connection:
    - Valid session token receives CONNECTION_ESTABLISHED.
    - PING heartbeat returns PONG.
    - Invalid token is rejected.
    """
    cust = test_setup["cust_user"]
    cust_session = create_user_session(db_session, cust.id)

    # 1. Valid token connect
    with client.websocket_connect(f"/api/v1/ws?token={cust_session.session_id}") as websocket:
        # Handshake confirmation
        handshake = websocket.receive_json()
        assert handshake["type"] == "CONNECTION_ESTABLISHED"
        assert handshake["data"]["user_id"] == cust.id
        assert handshake["data"]["role"] == "CUSTOMER"

        # Heartbeat test
        websocket.send_json({"type": "PING", "data": 12345})
        pong = websocket.receive_json()
        assert pong["type"] == "PONG"
        assert pong["echo"] == 12345

    # 2. Invalid token connect rejection
    with pytest.raises(Exception):
        with client.websocket_connect("/api/v1/ws?token=invalid_nonexistent_token"):
            pass


def test_realtime_order_lifecycle_event_delivery(client: TestClient, db_session: Session, test_setup):
    """
    Customer places order -> Kitchen Owner & Admin receive ORDER_CREATED.
    Kitchen Owner accepts order -> Customer & Admin receive ORDER_STATUS_CHANGED.
    """
    cust = test_setup["cust_user"]
    ko_user = test_setup["ko_user"]
    admin = test_setup["admin"]
    kitchen = test_setup["kitchen"]
    menu_item = test_setup["menu_item"]
    address = test_setup["address"]

    cust_session = create_user_session(db_session, cust.id)
    ko_session = create_user_session(db_session, ko_user.id)
    admin_session = create_user_session(db_session, admin.id)

    # Connect WebSocket for Kitchen Owner and Admin
    with client.websocket_connect(f"/api/v1/ws?token={ko_session.session_id}") as ko_ws, \
         client.websocket_connect(f"/api/v1/ws?token={admin_session.session_id}") as admin_ws, \
         client.websocket_connect(f"/api/v1/ws?token={cust_session.session_id}") as cust_ws:

        # Receive handshake messages
        assert ko_ws.receive_json()["type"] == "CONNECTION_ESTABLISHED"
        assert admin_ws.receive_json()["type"] == "CONNECTION_ESTABLISHED"
        assert cust_ws.receive_json()["type"] == "CONNECTION_ESTABLISHED"

        # Customer places an order via API
        order_payload = {
            "kitchen_id": kitchen.id,
            "delivery_address_id": address.id,
            "items": [{"menu_item_id": menu_item.id, "quantity": 2}],
            "payment_method": "ONLINE",
        }
        res_place = client.post(
            "/api/v1/customer/orders",
            json=order_payload,
            headers={"Authorization": f"Bearer {cust_session.session_id}"}
        )
        assert res_place.status_code == 201
        order_id = res_place.json()["id"]

        # Kitchen owner should receive ORDER_CREATED event!
        ko_event = ko_ws.receive_json()
        assert ko_event["type"] == "ORDER_CREATED"
        assert ko_event["data"]["order_id"] == order_id
        assert ko_event["data"]["kitchen_id"] == kitchen.id

        # Admin receives events (both NOTIFICATION_NEW and ORDER_CREATED)
        admin_events = []
        for _ in range(4):
            ev = admin_ws.receive_json()
            admin_events.append(ev)
            if ev["type"] == "ORDER_CREATED":
                break
        assert any(e["type"] == "ORDER_CREATED" and e["data"]["order_id"] == order_id for e in admin_events), f"Received: {[e['type'] for e in admin_events]}"

        # Customer should receive ORDER_CREATED confirmation event!
        cust_event = cust_ws.receive_json()
        assert cust_event["type"] == "ORDER_CREATED"
        assert cust_event["data"]["order_id"] == order_id

        # Now Kitchen Owner accepts the order
        res_accept = client.post(
            f"/api/v1/kitchen/orders/{order_id}/accept",
            headers={"Authorization": f"Bearer {ko_session.session_id}"}
        )
        assert res_accept.status_code == 200

        # Customer receives ORDER_STATUS_CHANGED!
        cust_status_event = cust_ws.receive_json()
        assert cust_status_event["type"] == "ORDER_STATUS_CHANGED"
        assert cust_status_event["data"]["order_id"] == order_id
        assert cust_status_event["data"]["status"] == "KITCHEN_ACCEPTED"

        # Admin receives ORDER_STATUS_CHANGED!
        admin_accept_events = []
        for _ in range(3):
            ev = admin_ws.receive_json()
            admin_accept_events.append(ev)
            if ev["type"] == "ORDER_STATUS_CHANGED":
                break
        assert any(e["type"] == "ORDER_STATUS_CHANGED" and e["data"]["status"] == "KITCHEN_ACCEPTED" for e in admin_accept_events)


def test_http_polling_fallback_and_rbac(client: TestClient, db_session: Session, test_setup):
    """
    Test GET /api/v1/events/poll fallback with strict RBAC filtering.
    """
    cust = test_setup["cust_user"]
    ko_user = test_setup["ko_user"]
    admin = test_setup["admin"]
    kitchen = test_setup["kitchen"]

    cust_session = create_user_session(db_session, cust.id)
    ko_session = create_user_session(db_session, ko_user.id)
    admin_session = create_user_session(db_session, admin.id)

    # Publish an event specifically for kitchen owner
    start_time = time.time() - 1.0
    ws_manager.publish_event(
        event_type="INVENTORY_UPDATED",
        data={"kitchen_id": kitchen.id, "ingredient": "Basmati Rice", "current_stock": 42.0},
        target_kitchen_id=kitchen.id,
    )

    # Kitchen Owner polls: sees the inventory event
    res_ko_poll = client.get(
        f"/api/v1/events/poll?since={start_time}",
        headers={"Authorization": f"Bearer {ko_session.session_id}"}
    )
    assert res_ko_poll.status_code == 200
    events_ko = res_ko_poll.json()["events"]
    assert any(e["type"] == "INVENTORY_UPDATED" and e["data"]["kitchen_id"] == kitchen.id for e in events_ko)

    # Customer polls: MUST NOT see kitchen's private inventory event (RBAC isolation!)
    res_cust_poll = client.get(
        f"/api/v1/events/poll?since={start_time}",
        headers={"Authorization": f"Bearer {cust_session.session_id}"}
    )
    assert res_cust_poll.status_code == 200
    events_cust = res_cust_poll.json()["events"]
    assert not any(e["type"] == "INVENTORY_UPDATED" and e["data"]["kitchen_id"] == kitchen.id for e in events_cust)

    # Admin polls: sees all events
    res_admin_poll = client.get(
        f"/api/v1/events/poll?since={start_time}",
        headers={"Authorization": f"Bearer {admin_session.session_id}"}
    )
    assert res_admin_poll.status_code == 200
    events_admin = res_admin_poll.json()["events"]
    assert any(e["type"] == "INVENTORY_UPDATED" and e["data"]["kitchen_id"] == kitchen.id for e in events_admin)
