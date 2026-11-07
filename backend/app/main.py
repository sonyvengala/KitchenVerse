"""
FastAPI Main Application Entrypoint.
KitchenVerse Backend.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core.config import settings
from backend.app.api.api_v1 import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Register running asyncio event loop for thread-safe WebSocket broadcasts
    import asyncio
    from backend.app.websockets.connection_manager import ws_manager
    ws_manager.set_event_loop(asyncio.get_running_loop())

    # Startup operations: ensure database schema is initialized
    from backend.app.core.database import Base, engine, SessionLocal, ensure_schema_compatibility
    import backend.app.models
    Base.metadata.create_all(bind=engine)
    ensure_schema_compatibility(engine)

    # Idempotent Admin Account Bootstrap
    from backend.app.models.user import User
    from backend.app.models.enums import UserRole
    from backend.app.core.security import get_password_hash
    import uuid

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == UserRole.ADMIN).first()
        if not admin:
            admin_user = User(
                id=str(uuid.uuid4()),
                email="admin@cloudkitchen.com",
                hashed_password=get_password_hash("AdminPass123!"),
                full_name="Super Administrator",
                phone_number="+919999999999",
                role=UserRole.ADMIN,
                is_active=True,
                is_verified=True,
            )
            db.add(admin_user)
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

    yield
    # Shutdown cleanup


app = FastAPI(
    title=settings.APP_NAME,
    description="Multi-tenant Cloud Kitchen management and customer ordering platform with real-time operations and ML demand forecasting.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS Middleware (credentials=True required for secure HttpOnly cookie session auth)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def browser_admin_redirect_middleware(request, call_next):
    """
    If a web browser directly requests an /admin UI page on the backend port
    (e.g. http://localhost:8000/admin/notifications with Accept: text/html),
    redirect the browser to the Frontend Admin Portal (http://localhost:3000/admin/notifications).
    API calls (Accept: application/json, fetch, or XHR) continue directly to the backend.
    """
    path = request.url.path
    if path == "/admin" or path.startswith("/admin/"):
        accept = request.headers.get("accept", "")
        if "text/html" in accept and "application/json" not in accept:
            from fastapi.responses import RedirectResponse
            frontend_url = settings.FRONTEND_URL.rstrip("/")
            target_url = f"{frontend_url}{path}"
            if request.url.query:
                target_url += f"?{request.url.query}"
            return RedirectResponse(url=target_url, status_code=307)

    return await call_next(request)

# Mount API routers (both /api/v1 and /api for compatibility)
app.include_router(api_router, prefix="/api/v1")
app.include_router(api_router, prefix="/api")

# Static files for uploaded/generated images
import os
from fastapi.staticfiles import StaticFiles
uploads_dir = os.path.join(os.getcwd(), "data", "uploads")
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

from backend.app.api.routes.admin import router as admin_router
app.include_router(admin_router)

from backend.app.api.routes.websockets import router as ws_router
app.include_router(ws_router)


@app.get("/")
def read_root():
    return {
        "platform": settings.APP_NAME,
        "message": f"Welcome to {settings.APP_NAME} API",
        "environment": settings.APP_ENV,
        "api_docs": "/docs",
        "api_v1": "/api/v1"
    }


from backend.app.api.routes.health import check_health
from backend.app.core.database import get_db
from sqlalchemy.orm import Session
from fastapi import Depends

@app.get("/health", tags=["Health"])
def root_health_alias(db: Session = Depends(get_db)):
    """Lightweight root health alias for load balancers and container probes."""
    return check_health(db)
