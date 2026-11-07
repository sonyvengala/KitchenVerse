"""API dependencies for authentication and authorization."""
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import decode_token
from backend.app.database.session import get_db
from backend.app.models.user import User, UserRole

# Bearer token scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Extract and validate the current user from the JWT token.
    Raises 401 if token is invalid or user not found.
    """
    token = credentials.credentials
    payload = decode_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.status.value == "SUSPENDED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is suspended",
        )

    if user.status.value == "INACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Ensure the current user has verified their email.
    """
    if not current_user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please verify your email first.",
        )
    return current_user


def require_role(allowed_roles: list):
    """
    Dependency factory that checks if the user has one of the allowed roles.
    
    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_role([UserRole.ADMIN]))])
    """
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in [UserRole(r) if isinstance(r, str) else r for r in allowed_roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {[r.value if isinstance(r, UserRole) else r for r in allowed_roles]}",
            )
        return current_user
    return role_checker


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require ADMIN role."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin role required.",
        )
    return current_user


async def require_kitchen_owner(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require KITCHEN_OWNER role."""
    if current_user.role != UserRole.KITCHEN_OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Kitchen owner role required.",
        )
    return current_user


async def require_customer(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require CUSTOMER role."""
    if current_user.role != UserRole.CUSTOMER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Customer role required.",
        )
    return current_user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    Optionally extract user from token. Returns None if no valid token.
    """
    if credentials is None:
        return None

    payload = decode_token(credentials.credentials)
    if payload is None or payload.get("type") != "access":
        return None

    user_id = payload.get("sub")
    if user_id is None:
        return None

    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    return result.scalar_one_or_none()
