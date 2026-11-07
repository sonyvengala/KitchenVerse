"""
FastAPI dependencies for database sessions, current authenticated user,
and server-side Role-Based Access Control (RBAC).
"""
from typing import List, Optional
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.session import get_active_session
from backend.app.models.enums import UserRole
from backend.app.models.user import User, UserSession


def get_session_token_from_request(request: Request) -> Optional[str]:
    """
    Extract session ID from Authorization: Bearer <session_id> header first (explicit client token),
    or fallback to HttpOnly session cookie (ambient browser session).
    """
    # 1. Authorization Header (Explicit client/tab token - takes precedence)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        hdr_token = auth_header[7:].strip()
        if hdr_token and hdr_token not in ("null", "undefined", "cookie-session"):
            return hdr_token

    # 2. HttpOnly Cookie fallback (Ambient session for direct browser requests)
    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if token:
        return token

    return None


def get_current_session(
    request: Request,
    db: Session = Depends(get_db)
) -> UserSession:
    """Retrieve and validate the active database-backed server-side session."""
    session_id = get_session_token_from_request(request)
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    session = get_active_session(db, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session is invalid or has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return session


def get_current_user(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db)
) -> User:
    """Retrieve the current active authenticated user."""
    user = db.query(User).filter(User.id == session.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )
    return user


def require_roles(allowed_roles: List[UserRole]):
    """Server-side RBAC dependency factory."""
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: requires one of roles {[r.value for r in allowed_roles]}",
            )
        return current_user

    return role_checker


# Convenient RBAC dependencies
require_customer = require_roles([UserRole.CUSTOMER])
require_kitchen_owner = require_roles([UserRole.KITCHEN_OWNER])
require_admin = require_roles([UserRole.ADMIN])
require_kitchen_or_admin = require_roles([UserRole.KITCHEN_OWNER, UserRole.ADMIN])
require_any_authenticated = get_current_user
