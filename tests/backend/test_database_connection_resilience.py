"""
Automated tests for database URL normalization and production connection failure safety.
Guarantees:
  1. Render/Heroku legacy 'postgres://' URLs are safely normalized to 'postgresql://'.
  2. Silent fallback to SQLite is strictly disabled in production (APP_ENV=production).
  3. Production raises a clear RuntimeError if PostgreSQL is unreachable.
  4. Development environment retains safe fallback for local development.
"""
import pytest
from sqlalchemy import text
from backend.app.core.database import normalize_database_url, create_app_engine


def test_normalize_database_url_render_postgres_scheme():
    # Render default format
    render_url = "postgres://kitchenverse_user:secret_pass@dpg-abc-a.ohio-postgres.render.com/kitchenverse"
    expected = "postgresql://kitchenverse_user:secret_pass@dpg-abc-a.ohio-postgres.render.com/kitchenverse"
    assert normalize_database_url(render_url) == expected


def test_normalize_database_url_already_standard():
    pg_url = "postgresql://cloudkitchen_user:pass@localhost:5432/cloudkitchen_db"
    assert normalize_database_url(pg_url) == pg_url

    psycopg_url = "postgresql+psycopg://user:pass@localhost:5432/db"
    assert normalize_database_url(psycopg_url) == psycopg_url


def test_normalize_database_url_sqlite_and_edge_cases():
    assert normalize_database_url("sqlite:///./cloudkitchen_local.db") == "sqlite:///./cloudkitchen_local.db"
    assert normalize_database_url("sqlite:///:memory:") == "sqlite:///:memory:"
    assert normalize_database_url("") == ""
    assert normalize_database_url(None) is None
    # Trimming whitespace
    assert normalize_database_url("  postgres://user:pass@host/db  ") == "postgresql://user:pass@host/db"


def test_production_fails_fast_on_unreachable_postgresql():
    """In production, an unreachable PostgreSQL connection must raise RuntimeError and never fall back to SQLite."""
    unreachable_pg_url = "postgresql://user:invalid@127.0.0.1:54399/unreachable_db"
    with pytest.raises(RuntimeError) as exc_info:
        create_app_engine(unreachable_pg_url, is_production=True)

    err_msg = str(exc_info.value)
    assert "Silent fallback to SQLite is disabled in production" in err_msg


def test_development_falls_back_to_sqlite():
    """In development, an unreachable PostgreSQL connection falls back to local SQLite without crashing."""
    unreachable_pg_url = "postgresql://user:invalid@127.0.0.1:54399/unreachable_db"
    engine = create_app_engine(unreachable_pg_url, is_production=False)
    assert engine is not None
    assert engine.dialect.name == "sqlite"


def test_valid_sqlite_engine_creation_both_modes():
    """Valid SQLite engine creates successfully in both production and development."""
    engine_dev = create_app_engine("sqlite:///:memory:", is_production=False)
    assert engine_dev.dialect.name == "sqlite"

    engine_prod = create_app_engine("sqlite:///:memory:", is_production=True)
    assert engine_prod.dialect.name == "sqlite"

    with engine_prod.connect() as conn:
        res = conn.execute(text("SELECT 1")).scalar()
        assert res == 1

