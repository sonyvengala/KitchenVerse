"""
Database-backed server-side session management.
Ensures session persistence, TTL expiration, and real server-side invalidation.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.core.security import generate_session_id
from backend.app.models.user import UserSession


def create_user_session(
    db: Session,
    user_id: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    max_age_seconds: Optional[int] = None
) -> UserSession:
    """Create and persist a new user session."""
    session_id = generate_session_id()
    ttl = max_age_seconds or settings.SESSION_MAX_AGE_SECONDS
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl)

    user_session = UserSession(
        session_id=session_id,
        user_id=user_id,
        expires_at=expires_at,
        is_revoked=False,
        ip_address=ip_address,
        user_agent=user_agent
    )
    db.add(user_session)
    db.commit()
    db.refresh(user_session)
    return user_session


def get_active_session(db: Session, session_id: str) -> Optional[UserSession]:
    """Retrieve an active, unexpired, and non-revoked session."""
    if not session_id:
        return None

    now = datetime.now(timezone.utc)
    session = db.query(UserSession).filter(
        UserSession.session_id == session_id,
        UserSession.is_revoked == False
    ).first()

    if not session:
        return None

    # Handle timezone-aware or naive comparison
    session_expiry = session.expires_at
    if session_expiry.tzinfo is None:
        session_expiry = session_expiry.replace(tzinfo=timezone.utc)

    if session_expiry < now:
        # Session expired: mark revoked
        session.is_revoked = True
        db.commit()
        return None

    return session


def revoke_session(db: Session, session_id: str) -> bool:
    """Explicitly invalidate a server-side session (real logout)."""
    session = db.query(UserSession).filter(UserSession.session_id == session_id).first()
    if session:
        session.is_revoked = True
        db.commit()
        return True
    return False


def revoke_all_user_sessions(db: Session, user_id: str) -> int:
    """Invalidate all active sessions for a user (e.g. after password change)."""
    count = db.query(UserSession).filter(
        UserSession.user_id == user_id,
        UserSession.is_revoked == False
    ).update({"is_revoked": True})
    db.commit()
    return count
