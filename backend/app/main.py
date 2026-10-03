"""Main FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.database.session import init_db, close_db
from app.api.auth import router as auth_router

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info(f"Starting {settings.APP_NAME}...")
    logger.info(f"Environment: {settings.APP_ENV}")
    logger.info(f"Email provider: {settings.EMAIL_PROVIDER}")

    # In development, auto-create tables if database is available
    if settings.APP_ENV == "development":
        try:
            await init_db()
            logger.info("Database tables initialized (development mode)")
        except Exception as e:
            logger.warning(f"Could not initialize database: {e}")
            logger.warning("Database features will not be available until database is configured")

    yield

    await close_db()
    logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="Unified Cloud Kitchen Platform API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors safely without exposing internals."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred"},
    )


# Include routers
app.include_router(auth_router, prefix="/api")


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Application health check."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "environment": settings.APP_ENV,
    }


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """API root."""
    return {
        "message": f"Welcome to {settings.APP_NAME} API",
        "version": "0.1.0",
        "docs": "/docs" if settings.DEBUG else "Documentation disabled in production",
    }
