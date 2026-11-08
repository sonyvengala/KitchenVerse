"""
Database connection, engine configuration, and session management.
Supports PostgreSQL with fallback for testing and development environments.
"""
import os
from typing import Generator
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from backend.app.core.config import settings

# Determine database URL and environment
def normalize_database_url(url: str) -> str:
    """
    Normalize database connection URLs for SQLAlchemy 2.0+ compatibility.
    Converts legacy 'postgres://' URLs (provided by Render/Heroku) to 'postgresql://'.
    """
    if not url:
        return url
    trimmed = str(url).strip()
    if trimmed.startswith("postgres://"):
        return "postgresql://" + trimmed[len("postgres://"):]
    return trimmed


def create_app_engine(url: str, is_production: bool = False):
    """
    Create SQLAlchemy engine with connection verification.
    In production (is_production=True), fails immediately with RuntimeError
    if PostgreSQL connection fails, preventing silent SQLite fallback and data loss.
    In development, falls back to local SQLite if PostgreSQL is unreachable.
    """
    norm_url = normalize_database_url(url)
    connect_args = {}
    if norm_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    elif norm_url.startswith("postgresql"):
        connect_args.setdefault("connect_timeout", 10)

    try:
        eng = create_engine(
            norm_url,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False,
            connect_args=connect_args
        )
        if not norm_url.startswith("sqlite"):
            with eng.connect() as test_conn:
                pass
        return eng
    except Exception as e:
        if is_production:
            import logging
            logging.getLogger("uvicorn.error").critical(
                f"FATAL: Production database connection failed: {e}. "
                "Silent fallback to SQLite is disabled in production."
            )
            raise RuntimeError(
                f"Production database connection failed: {e}. "
                "Silent fallback to SQLite is disabled in production."
            ) from e

        # Non-production (development / test) fallback only
        fallback_url = "sqlite:///./cloudkitchen_local.db"
        return create_engine(
            fallback_url,
            connect_args={"check_same_thread": False},
            pool_pre_ping=True
        )


raw_database_url = os.getenv("DATABASE_URL", settings.DATABASE_URL)
database_url = normalize_database_url(raw_database_url)
is_production_env = os.getenv("APP_ENV", str(settings.APP_ENV)).lower() == "production"

engine = create_app_engine(database_url, is_production=is_production_env)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for SQLAlchemy ORM models
Base = declarative_base()


PROTECTED_REAL_EMAILS = {
    "sonyvengala7@gmail.com",
    "sonyvengala04@gmail.com",
    "b23it030@kitsw.ac.in",
    "rohithkalli00@gmail.com",
    "rohithkalli743@gmail.com",
    "admin@cloudkitchen.com",
}


def is_protected_real_user_email(email: str) -> bool:
    """Identify if an email represents a protected real account that tests/scripts/admin actions must NEVER mutate or delete."""
    if not email:
        return False
    return email.strip().lower() in PROTECTED_REAL_EMAILS



@event.listens_for(Session, "before_flush")
def enforce_test_isolation_and_protect_real_users(session, flush_context, instances):
    """
    SAFETY GUARD:
    Prevents tests and automated scripts from modifying or deleting real user accounts.
    If a test or script attempts to mutate or delete a protected real user, aborts with a clear error.
    """
    from backend.app.models.user import User

    # 1. Inspect modified/dirty records
    for obj in session.dirty:
        if isinstance(obj, User):
            ins = inspect(obj)
            deleted_emails = ins.attrs.email.history.deleted
            original_email = deleted_emails[0] if deleted_emails else obj.email

            if is_protected_real_user_email(original_email) or is_protected_real_user_email(obj.email):
                critical_fields = ["hashed_password", "email", "role", "is_verified", "is_active"]
                changed_fields = [
                    f for f in critical_fields
                    if getattr(ins.attrs, f).history.has_changes()
                ]

                is_test_env = (
                    "PYTEST_CURRENT_TEST" in os.environ
                    or os.getenv("CLOUDKITCHEN_ENV") == "test"
                    or os.getenv("IS_TEST") == "1"
                )

                if is_test_env:
                    raise PermissionError(
                        f"TEST ISOLATION VIOLATION: Aborted attempt to modify protected real user '{original_email}'. "
                        f"Automated tests and scripts must NEVER mutate real user accounts. "
                        f"Attempted modifications: {changed_fields}. "
                        f"Use isolated test fixtures or dedicated test accounts instead."
                    )

                if changed_fields and not getattr(session, "_allow_auth_service_update", False):
                    raise PermissionError(
                        f"CRITICAL SECURITY GUARD: Unauthorized direct modification of real user account '{original_email}' "
                        f"for fields {changed_fields} is strictly blocked. "
                        f"Automated scripts cannot mutate real accounts or passwords directly."
                    )

    # 2. Inspect deleted records
    for obj in session.deleted:
        if isinstance(obj, User):
            if is_protected_real_user_email(obj.email):
                raise PermissionError(
                    f"TEST ISOLATION VIOLATION: Aborted attempt to delete protected real user '{obj.email}'. "
                    f"Real user accounts cannot be deleted by tests or automated scripts."
                )


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a SQLAlchemy database session.
    Automatically handles session closing and rollback on unhandled exceptions.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def ensure_schema_compatibility(target_engine=None):
    """Safely and idempotently ensure new columns and tables exist across PostgreSQL and SQLite."""
    use_engine = target_engine or engine
    from sqlalchemy import text
    try:
        Base.metadata.create_all(bind=use_engine)
        with use_engine.connect() as conn:
            insp = inspect(use_engine)
            if "orders" in insp.get_table_names():
                cols = [c["name"] for c in insp.get_columns("orders")]
                if "delivery_distance_km" not in cols:
                    conn.execute(text("ALTER TABLE orders ADD COLUMN delivery_distance_km FLOAT"))
                if "pricing_breakdown_json" not in cols:
                    conn.execute(text("ALTER TABLE orders ADD COLUMN pricing_breakdown_json TEXT"))
            if "menu_item_ingredients" in insp.get_table_names():
                cols = [c["name"] for c in insp.get_columns("menu_item_ingredients")]
                if "unit" not in cols:
                    conn.execute(text("ALTER TABLE menu_item_ingredients ADD COLUMN unit VARCHAR(20)"))
            if "ingredients" in insp.get_table_names():
                cols = [c["name"] for c in insp.get_columns("ingredients")]
                if "unit_cost" not in cols:
                    conn.execute(text("ALTER TABLE ingredients ADD COLUMN unit_cost FLOAT"))
            conn.commit()
    except Exception:
        pass
