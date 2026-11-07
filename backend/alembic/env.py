"""Alembic environment configuration."""
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Add project root and backend to path so we can import backend.app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.core.database import Base
import backend.app.models
from backend.app.core.config import settings

# Alembic Config object
config = context.config

# Override sqlalchemy.url from environment or settings
sync_url = getattr(settings, "DATABASE_URL_SYNC", None) or os.getenv("DATABASE_URL_SYNC")
if not sync_url:
    raw_url = os.getenv("DATABASE_URL") or str(settings.DATABASE_URL)
    sync_url = str(raw_url).replace("+asyncpg", "").replace("+psycopg", "")

if "localhost:5433" in sync_url or "user:password" in sync_url or "postgres:postgres" in sync_url:
    sync_url = "postgresql://cloud_kitchen_user:Roso%400404@localhost:5432/cloud_kitchen"

# ConfigParser requires escaping '%' as '%%' for interpolation
escaped_url = sync_url.replace("%%", "%").replace("%", "%%")
config.set_main_option("sqlalchemy.url", escaped_url)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata for autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
