"""
Role-Based Access Control verification routes.
Demonstrates server-side route protection across CUSTOMER, KITCHEN_OWNER, and ADMIN roles.
"""
from fastapi import APIRouter, Depends
from backend.app.core.deps import require_customer, require_kitchen_owner, require_admin
from backend.app.models.user import User

router = APIRouter(prefix="/test-rbac", tags=["RBAC Test"])


@router.get("/customer")
def customer_only_route(user: User = Depends(require_customer)):
    return {"message": f"Hello Customer {user.full_name}", "role": user.role.value}


@router.get("/kitchen")
def kitchen_only_route(user: User = Depends(require_kitchen_owner)):
    return {"message": f"Hello Kitchen Owner {user.full_name}", "role": user.role.value}


@router.get("/admin")
def admin_only_route(user: User = Depends(require_admin)):
    return {"message": f"Hello Admin {user.full_name}", "role": user.role.value}
