"""
Health check endpoints for load balancers and system monitoring.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.core.database import get_db

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", status_code=status.HTTP_200_OK)
def check_health(db: Session = Depends(get_db)):
    """
    Check application health and database connectivity.
    """
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "app": settings.APP_NAME,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": db_status
    }
