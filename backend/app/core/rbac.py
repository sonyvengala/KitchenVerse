"""
Role-Based Access Control (RBAC) definitions and permission checks.
"""
from typing import List
from backend.app.models.enums import UserRole
from backend.app.models.user import User


class RBACPermissionError(Exception):
    pass


def check_user_role(user: User, allowed_roles: List[UserRole]) -> bool:
    """Verify if user has one of the allowed roles."""
    if not user or not user.is_active:
        return False
    return user.role in allowed_roles


def is_admin(user: User) -> bool:
    return check_user_role(user, [UserRole.ADMIN])


def is_kitchen_owner(user: User) -> bool:
    return check_user_role(user, [UserRole.KITCHEN_OWNER])


def is_customer(user: User) -> bool:
    return check_user_role(user, [UserRole.CUSTOMER])
