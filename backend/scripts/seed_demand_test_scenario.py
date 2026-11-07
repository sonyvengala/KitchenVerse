"""
Controlled CloudKitchen Demand-Prediction Test Scenario Seeder.

This script sets up a isolated validation scenario for:
  - Customers: rohithkalli00@gmail.com, rohithkalli743@gmail.com
  - Kitchen Owner: b23it030@kitsw.ac.in

Strict Rules:
  - Idempotent: Can be run multiple times safely.
  - Zero Emails: Bypasses live SMTP dispatch completely.
  - Test Isolation: All generated orders are marked is_test=True with 'TEST-ORD-KITS-...' order numbers.
  - No Overwrite: Preserves any existing accounts and passwords if already present.
  - Operational Forecast Compliance: Creates orders across 4 operating days with distinct menu items,
    satisfying MIN_PROJECTION_ORDERS (>= 5) and MIN_PROJECTION_DAYS (>= 3).
"""
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

# Suppress live email dispatch
os.environ["EMAIL_PROVIDER"] = "none"

from backend.app.core.database import SessionLocal
from backend.app.core.security import get_password_hash
from backend.app.models.enums import UserRole, OrderStatus, PaymentStatus, InventoryStatus
from backend.app.models.user import User, KitchenProfile, CustomerProfile, Address
from backend.app.models.menu import MenuItem, Ingredient, MenuItemIngredient
from backend.app.models.inventory import Inventory
from backend.app.models.order import Order, OrderItem, Payment


def seed_test_scenario(plain_password: str = "Test@Pass1234") -> Dict[str, Any]:
    db = SessionLocal()
    try:
        created_records: Dict[str, List[str]] = {
            "users": [],
            "kitchens": [],
            "addresses": [],
            "ingredients": [],
            "menu_items": [],
            "recipes": [],
            "inventory": [],
            "orders": [],
        }

        # 1. Kitchen Owner Account: b23it030@kitsw.ac.in
        owner_email = "b23it030@kitsw.ac.in"
        owner = db.query(User).filter(User.email == owner_email).first()
        if not owner:
            owner = User(
                id=str(uuid.uuid4()),
                email=owner_email,
                hashed_password=get_password_hash(plain_password),
                full_name="Rohith Kalli (Kitchen Owner)",
                phone_number="+91 9876543210",
                role=UserRole.KITCHEN_OWNER,
                is_active=True,
                is_verified=True,
            )
            db.add(owner)
            db.flush()
            created_records["users"].append(f"Kitchen Owner: {owner_email} (ID: {owner.id})")
        else:
            # Preserve existing credentials and data
            pass

        # 2. Kitchen Profile for Owner
        kitchen = db.query(KitchenProfile).filter(KitchenProfile.user_id == owner.id).first()
        if not kitchen:
            kitchen = KitchenProfile(
                id=str(uuid.uuid4()),
                user_id=owner.id,
                kitchen_name="KITS Gourmet Cloud Kitchen",
                description="Test kitchen providing authentic Hyderabadi Biryani and paneer specialties.",
                address="Near KITS Warangal Campus, Yerragattu Hill",
                city="Warangal",
                state="Telangana",
                postal_code="506015",
                phone="+91 9876543210",
                latitude=18.0012,
                longitude=79.5523,
                cuisine="Indian, Biryani, Curries",
                is_open=True,
                is_approved=True,
                approval_status="APPROVED",
                rating=4.9,
                rating_count=18,
            )
            db.add(kitchen)
            db.flush()
            created_records["kitchens"].append(f"{kitchen.kitchen_name} (ID: {kitchen.id})")

        # 3. Customer 1 Account: rohithkalli00@gmail.com
        cust1_email = "rohithkalli00@gmail.com"
        cust1 = db.query(User).filter(User.email == cust1_email).first()
        if not cust1:
            cust1 = User(
                id=str(uuid.uuid4()),
                email=cust1_email,
                hashed_password=get_password_hash(plain_password),
                full_name="Rohith Kalli Primary",
                phone_number="+91 9123456780",
                role=UserRole.CUSTOMER,
                is_active=True,
                is_verified=True,
            )
            db.add(cust1)
            db.flush()
            cust1_prof = CustomerProfile(user_id=cust1.id, dietary_preferences="Non-Vegetarian")
            db.add(cust1_prof)
            created_records["users"].append(f"Customer 1: {cust1_email} (ID: {cust1.id})")

        # Customer 1 Address
        addr1 = db.query(Address).filter(Address.user_id == cust1.id).first()
        if not addr1:
            addr1 = Address(
                id=str(uuid.uuid4()),
                user_id=cust1.id,
                address_line1="Hostel Block B, Room 204, KITS Campus",
                city="Warangal",
                state="Telangana",
                postal_code="506015",
                is_default=True,
            )
            db.add(addr1)
            db.flush()
            created_records["addresses"].append(f"Address for {cust1_email}")

        # 4. Customer 2 Account: rohithkalli743@gmail.com
        cust2_email = "rohithkalli743@gmail.com"
        cust2 = db.query(User).filter(User.email == cust2_email).first()
        if not cust2:
            cust2 = User(
                id=str(uuid.uuid4()),
                email=cust2_email,
                hashed_password=get_password_hash(plain_password),
                full_name="Rohith Kalli Secondary",
                phone_number="+91 9123456789",
                role=UserRole.CUSTOMER,
                is_active=True,
                is_verified=True,
            )
            db.add(cust2)
            db.flush()
            cust2_prof = CustomerProfile(user_id=cust2.id, dietary_preferences="Vegetarian")
            db.add(cust2_prof)
            created_records["users"].append(f"Customer 2: {cust2_email} (ID: {cust2.id})")

        # Customer 2 Address
        addr2 = db.query(Address).filter(Address.user_id == cust2.id).first()
        if not addr2:
            addr2 = Address(
                id=str(uuid.uuid4()),
                user_id=cust2.id,
                address_line1="House 4-12, Hasanparthy Main Road",
                city="Warangal",
                state="Telangana",
                postal_code="506015",
                is_default=True,
            )
            db.add(addr2)
            db.flush()
            created_records["addresses"].append(f"Address for {cust2_email}")

        # 5. Ingredients for KITS Cloud Kitchen
        ingredient_defs = [
            ("Basmati Rice", "kg", 45.0, 10.0, 30.0),
            ("Fresh Paneer", "kg", 25.0, 5.0, 20.0),
            ("Biryani Spices & Masala", "kg", 15.0, 3.0, 10.0),
            ("Pure Cooking Ghee", "l", 20.0, 5.0, 15.0),
        ]
        ing_map: Dict[str, Ingredient] = {}
        for name, unit, stock, min_thresh, reorder_qty in ingredient_defs:
            ing = db.query(Ingredient).filter(
                Ingredient.kitchen_id == kitchen.id,
                Ingredient.name == name
            ).first()
            if not ing:
                ing = Ingredient(
                    id=str(uuid.uuid4()),
                    kitchen_id=kitchen.id,
                    name=name,
                    unit=unit,
                    current_stock=stock,
                    minimum_stock_threshold=min_thresh,
                    reorder_quantity=reorder_qty,
                )
                db.add(ing)
                db.flush()
                # Create Inventory tracking record
                inv = Inventory(
                    id=str(uuid.uuid4()),
                    kitchen_id=kitchen.id,
                    ingredient_id=ing.id,
                    quantity=stock,
                    unit=unit,
                    status=InventoryStatus.AVAILABLE,
                )
                db.add(inv)
                created_records["ingredients"].append(f"{name} ({unit})")
                created_records["inventory"].append(f"Inventory: {name}")
            ing_map[name] = ing

        # 6. Menu Items for KITS Cloud Kitchen
        menu_defs = [
            ("Special Paneer Biryani", "Fragrant dum biryani with marinated paneer cubes and rich saffron aromas", "Biryani", "Indian", 240.0, True),
            ("Paneer Tikka Platter", "Charcoal roasted spiced cottage cheese with mint chutney", "Starters", "Indian", 190.0, True),
            ("Masala Spiced Chai", "Cardamom and ginger brewed fresh milk tea", "Beverages", "Indian", 40.0, True),
        ]
        item_map: Dict[str, MenuItem] = {}
        for name, desc, cat, cuisine, price, is_veg in menu_defs:
            m_item = db.query(MenuItem).filter(
                MenuItem.kitchen_id == kitchen.id,
                MenuItem.name == name
            ).first()
            if not m_item:
                m_item = MenuItem(
                    id=str(uuid.uuid4()),
                    kitchen_id=kitchen.id,
                    name=name,
                    description=desc,
                    category=cat,
                    cuisine=cuisine,
                    price=price,
                    is_available=True,
                    is_veg=is_veg,
                )
                db.add(m_item)
                db.flush()
                created_records["menu_items"].append(f"{name} (INR {price})")
            item_map[name] = m_item

        # 7. Recipe Definitions (MenuItemIngredient)
        recipe_links = [
            # Special Paneer Biryani requires: 0.25 kg Rice, 0.15 kg Paneer, 0.05 kg Spices, 0.03 l Ghee
            ("Special Paneer Biryani", "Basmati Rice", 0.25),
            ("Special Paneer Biryani", "Fresh Paneer", 0.15),
            ("Special Paneer Biryani", "Biryani Spices & Masala", 0.05),
            ("Special Paneer Biryani", "Pure Cooking Ghee", 0.03),
            # Paneer Tikka requires: 0.20 kg Paneer, 0.03 kg Spices
            ("Paneer Tikka Platter", "Fresh Paneer", 0.20),
            ("Paneer Tikka Platter", "Biryani Spices & Masala", 0.03),
        ]
        for m_name, ing_name, qty in recipe_links:
            m_obj = item_map.get(m_name)
            ing_obj = ing_map.get(ing_name)
            if m_obj and ing_obj:
                link = db.query(MenuItemIngredient).filter(
                    MenuItemIngredient.menu_item_id == m_obj.id,
                    MenuItemIngredient.ingredient_id == ing_obj.id
                ).first()
                if not link:
                    link = MenuItemIngredient(
                        id=str(uuid.uuid4()),
                        menu_item_id=m_obj.id,
                        ingredient_id=ing_obj.id,
                        quantity_required=qty,
                    )
                    db.add(link)
                    created_records["recipes"].append(f"{m_name} -> {ing_name} ({qty})")

        db.flush()

        # 8. Deterministic Test Orders (12 orders over 4 distinct dates)
        # Distinct Dates: 2026-10-06, 2026-10-07, 2026-10-08, 2026-10-09
        # Both customers participate, with varied item quantities to showcase popularity differentiation
        existing_test_orders = db.query(Order).filter(
            Order.kitchen_id == kitchen.id,
            Order.is_test == True,
            Order.order_number.like("TEST-ORD-KITS-%")
        ).count()

        if existing_test_orders == 0:
            order_plans = [
                # Day 1: 2026-10-06 (3 orders)
                {
                    "num": "TEST-ORD-KITS-001",
                    "cust": cust1,
                    "addr": addr1,
                    "dt": datetime(2026, 10, 6, 12, 30, tzinfo=timezone.utc),
                    "items": [("Special Paneer Biryani", 2), ("Masala Spiced Chai", 2)],
                },
                {
                    "num": "TEST-ORD-KITS-002",
                    "cust": cust2,
                    "addr": addr2,
                    "dt": datetime(2026, 10, 6, 13, 15, tzinfo=timezone.utc),
                    "items": [("Special Paneer Biryani", 1), ("Paneer Tikka Platter", 1)],
                },
                {
                    "num": "TEST-ORD-KITS-003",
                    "cust": cust1,
                    "addr": addr1,
                    "dt": datetime(2026, 10, 6, 20, 0, tzinfo=timezone.utc),
                    "items": [("Paneer Tikka Platter", 2), ("Masala Spiced Chai", 1)],
                },
                # Day 2: 2026-10-07 (3 orders)
                {
                    "num": "TEST-ORD-KITS-004",
                    "cust": cust2,
                    "addr": addr2,
                    "dt": datetime(2026, 10, 7, 12, 45, tzinfo=timezone.utc),
                    "items": [("Special Paneer Biryani", 3)],
                },
                {
                    "num": "TEST-ORD-KITS-005",
                    "cust": cust1,
                    "addr": addr1,
                    "dt": datetime(2026, 10, 7, 14, 0, tzinfo=timezone.utc),
                    "items": [("Special Paneer Biryani", 1), ("Masala Spiced Chai", 2)],
                },
                {
                    "num": "TEST-ORD-KITS-006",
                    "cust": cust2,
                    "addr": addr2,
                    "dt": datetime(2026, 10, 7, 19, 30, tzinfo=timezone.utc),
                    "items": [("Paneer Tikka Platter", 1), ("Special Paneer Biryani", 2)],
                },
                # Day 3: 2026-10-08 (3 orders)
                {
                    "num": "TEST-ORD-KITS-007",
                    "cust": cust1,
                    "addr": addr1,
                    "dt": datetime(2026, 10, 8, 12, 15, tzinfo=timezone.utc),
                    "items": [("Special Paneer Biryani", 2), ("Paneer Tikka Platter", 1)],
                },
                {
                    "num": "TEST-ORD-KITS-008",
                    "cust": cust2,
                    "addr": addr2,
                    "dt": datetime(2026, 10, 8, 13, 30, tzinfo=timezone.utc),
                    "items": [("Masala Spiced Chai", 4)],
                },
                {
                    "num": "TEST-ORD-KITS-009",
                    "cust": cust1,
                    "addr": addr1,
                    "dt": datetime(2026, 10, 8, 20, 15, tzinfo=timezone.utc),
                    "items": [("Special Paneer Biryani", 1), ("Masala Spiced Chai", 1)],
                },
                # Day 4: 2026-10-09 (3 orders)
                {
                    "num": "TEST-ORD-KITS-010",
                    "cust": cust2,
                    "addr": addr2,
                    "dt": datetime(2026, 10, 9, 12, 50, tzinfo=timezone.utc),
                    "items": [("Special Paneer Biryani", 3), ("Paneer Tikka Platter", 2)],
                },
                {
                    "num": "TEST-ORD-KITS-011",
                    "cust": cust1,
                    "addr": addr1,
                    "dt": datetime(2026, 10, 9, 14, 20, tzinfo=timezone.utc),
                    "items": [("Special Paneer Biryani", 2)],
                },
                {
                    "num": "TEST-ORD-KITS-012",
                    "cust": cust2,
                    "addr": addr2,
                    "dt": datetime(2026, 10, 9, 19, 45, tzinfo=timezone.utc),
                    "items": [("Paneer Tikka Platter", 1), ("Masala Spiced Chai", 2)],
                },
            ]

            for plan in order_plans:
                subtotal = 0.0
                order_id = str(uuid.uuid4())
                order_items_to_add = []

                for item_name, qty in plan["items"]:
                    m_item = item_map[item_name]
                    line_subtotal = round(float(m_item.price) * qty, 2)
                    subtotal += line_subtotal
                    order_items_to_add.append(
                        OrderItem(
                            id=str(uuid.uuid4()),
                            order_id=order_id,
                            menu_item_id=m_item.id,
                            item_name=m_item.name,
                            unit_price=float(m_item.price),
                            quantity=qty,
                            subtotal=line_subtotal,
                            created_at=plan["dt"],
                        )
                    )

                tax = round(subtotal * 0.05, 2)
                delivery_fee = 30.0
                total_amount = round(subtotal + tax + delivery_fee, 2)

                order = Order(
                    id=order_id,
                    order_number=plan["num"],
                    customer_id=plan["cust"].id,
                    kitchen_id=kitchen.id,
                    delivery_address_id=plan["addr"].id,
                    delivery_address_text=f"{plan['addr'].address_line1}, {plan['addr'].city}",
                    delivery_latitude=18.0015,
                    delivery_longitude=79.5530,
                    status=OrderStatus.DELIVERED,
                    subtotal=subtotal,
                    tax=tax,
                    delivery_fee=delivery_fee,
                    discount_amount=0.0,
                    is_test=True,  # STRICT TEST ISOLATION
                    total_amount=total_amount,
                    payment_status=PaymentStatus.SUCCESS,
                    special_instructions="TEST SCENARIO ORDER — Simulated customer activity",
                    created_at=plan["dt"],
                    updated_at=plan["dt"] + timedelta(minutes=45),
                )
                db.add(order)
                db.flush()

                for oi in order_items_to_add:
                    db.add(oi)

                payment = Payment(
                    id=str(uuid.uuid4()),
                    order_id=order_id,
                    payment_provider="SIMULATED",
                    transaction_reference=f"SIM-{plan['num']}",
                    amount=total_amount,
                    currency="INR",
                    status=PaymentStatus.SUCCESS,
                    created_at=plan["dt"],
                    updated_at=plan["dt"],
                )
                db.add(payment)
                created_records["orders"].append(
                    f"{plan['num']} | Cust: {plan['cust'].email.split('@')[0]} | INR {total_amount} | {plan['dt'].strftime('%Y-%m-%d %H:%M')}"
                )

        db.commit()
        return created_records

    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("SEEDING CONTROLLED DEMAND PREDICTION TEST SCENARIO")
    print("=" * 60)
    records = seed_test_scenario()
    for cat, items in records.items():
        print(f"\n[{cat.upper()}] ({len(items)} items):")
        for it in items:
            print(f"  + {it}")
    print("\nScenario successfully seeded with zero email dispatch!")
