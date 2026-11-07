from backend.app.core.database import SessionLocal
from backend.app.models.user import KitchenProfile
from backend.app.models.order import Order
from backend.app.models.enums import OrderStatus
from datetime import datetime, timezone, timedelta

db = SessionLocal()
days = 30
cutoff = datetime.now(timezone.utc) - timedelta(days=days)
EXCLUDED_STATUSES = (OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.REFUNDED)

kitchens = db.query(KitchenProfile).filter(KitchenProfile.is_approved == True).all()
print("=== KITCHEN DEMAND ===")
for k in kitchens:
    orders = db.query(Order).filter(
        Order.kitchen_id == k.id,
        Order.created_at >= cutoff,
        Order.is_test == False,
        ~Order.order_number.like('TEST-%'),
        ~Order.status.in_(EXCLUDED_STATUSES),
    ).all()
    count = len(orders)
    custs = len(set(o.customer_id for o in orders if o.customer_id))
    rev = round(sum(float(o.total_amount) for o in orders), 2)
    intensity = "HIGH" if count >= 20 else ("MEDIUM" if count >= 5 else "LOW")
    print(f"Kitchen: {k.kitchen_name} | Orders: {count} | Customers: {custs} | Revenue: Rs.{rev} | Intensity: {intensity}")

print("\n=== GEOGRAPHIC DEMAND AREAS ===")
orders = db.query(Order).filter(
    Order.created_at >= cutoff,
    Order.is_test == False,
    ~Order.order_number.like('TEST-%'),
    ~Order.status.in_(EXCLUDED_STATUSES),
).all()
areas = {}
for o in orders:
    addr = o.delivery_address
    if not addr:
        continue
    city = (addr.city or '').strip()
    if city.lower() in ('han', 'hanamkonda', 'hanumakonda'):
        city = 'Hanamkonda'
    elif city:
        city = city.title()
    else:
        city = 'Unspecified'
    postal = (addr.postal_code or '').strip()
    key = f"{city} — {postal}" if postal else city
    if key not in areas:
        areas[key] = {'count': 0, 'custs': set(), 'rev': 0.0}
    areas[key]['count'] += 1
    if o.customer_id:
        areas[key]['custs'].add(o.customer_id)
    areas[key]['rev'] += float(o.total_amount)

for key, val in areas.items():
    print(f"Area: {key} | Orders: {val['count']} | Customers: {len(val['custs'])} | Revenue: Rs.{round(val['rev'], 2)}")

db.close()
