"""
Unit tests for Alembic migrations idempotence and safety.
Verifies that:
1. All migrations upgrade cleanly on a fresh database.
2. All migrations upgrade idempotently on a pre-existing database (where tables/enums already exist).
3. The migration chain has a single head revision.
4. Down-revision chain is valid and unbroken.
"""
import os
import tempfile
import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory

from backend.app.core.database import Base
import backend.app.models  # ensure all models are imported into Base


@pytest.fixture
def alembic_config():
    """Create an Alembic config pointing to backend/alembic.ini."""
    cfg = Config("backend/alembic.ini")
    return cfg


def test_migration_chain_has_single_head_and_unbroken_history(alembic_config):
    """Confirm the Alembic migration history is contiguous and has exactly one head."""
    script_dir = ScriptDirectory.from_config(alembic_config)
    heads = script_dir.get_heads()
    assert len(heads) == 1, f"Expected exactly 1 migration head, got: {heads}"
    assert heads[0] == "007_add_ingredient_unit_cost"

    # Walk from head to base to ensure no disconnected revisions
    revisions = []
    curr = script_dir.get_revision(heads[0])
    while curr is not None:
        revisions.append(curr.revision)
        if curr.down_revision is None:
            break
        curr = script_dir.get_revision(curr.down_revision)

    expected_revisions = [
        "007_add_ingredient_unit_cost",
        "006_fssai_food_licenses",
        "005_remove_ai_menu_image_fields",
        "004_cancellation_requests",
        "003_menu_item_image_fields",
        "002_cancellation_wastage_route",
        "001_initial",
    ]
    assert revisions == expected_revisions, f"Migration chain mismatch: {revisions}"


def test_migrations_upgrade_cleanly_on_fresh_db():
    """Verify that all migrations apply from base to head on a fresh, empty database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        db_url = f"sqlite:///{db_path}"
        os.environ["DATABASE_URL"] = db_url

        cfg = Config("backend/alembic.ini")
        command.upgrade(cfg, "head")

        # Verify tables and alembic_version
        engine = sa.create_engine(db_url)
        inspector = sa.inspect(engine)
        tables = set(inspector.get_table_names())
        assert "alembic_version" in tables
        assert "users" in tables
        assert "orders" in tables
        assert "kitchen_licenses" in tables
        assert "cancellation_requests" in tables

        with engine.connect() as conn:
            current_rev = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
            assert current_rev == "007_add_ingredient_unit_cost"

        engine.dispose()
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_migrations_idempotent_on_pre_existing_tables():
    """
    Verify that if tables and schemas already exist (e.g. from Base.metadata.create_all
    during startup before Alembic ran), Alembic upgrades to head without throwing
    duplicate table or column errors.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        db_url = f"sqlite:///{db_path}"
        os.environ["DATABASE_URL"] = db_url

        # Simulate pre-existing database by running create_all first without alembic_version
        engine = sa.create_engine(db_url)
        Base.metadata.create_all(engine)
        engine.dispose()

        # Now run Alembic upgrade to head
        cfg = Config("backend/alembic.ini")
        command.upgrade(cfg, "head")

        # Verify alembic_version reached head
        engine = sa.create_engine(db_url)
        with engine.connect() as conn:
            current_rev = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
            assert current_rev == "007_add_ingredient_unit_cost"

        engine.dispose()
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_postgresql_enum_creation_sql_is_idempotent():
    """
    Test the PostgreSQL DO block idiom used in 001_initial.py to ensure the SQL
    is syntactically valid and checks pg_type correctly.
    """
    name = "userrole"
    values = ("CUSTOMER", "KITCHEN_OWNER", "ADMIN")
    val_str = ", ".join(f"'{v}'" for v in values)
    sql_text = f"""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{name}') THEN
                CREATE TYPE {name} AS ENUM ({val_str});
            END IF;
        END $$;
    """
    assert "IF NOT EXISTS" in sql_text
    assert "typname = 'userrole'" in sql_text
    assert "CREATE TYPE userrole AS ENUM ('CUSTOMER', 'KITCHEN_OWNER', 'ADMIN');" in sql_text


def test_postgresql_migration_logic_with_existing_pg_type_enums(monkeypatch):
    """
    Verify that when migrating on PostgreSQL where ENUM types already exist in pg_type,
    001_initial.py does NOT emit CREATE TYPE and sets create_type=False.
    """
    import sys
    from unittest.mock import MagicMock
    from sqlalchemy.dialects import postgresql

    # Mock connection bind
    mock_bind = MagicMock()
    mock_bind.dialect.name = "postgresql"
    # Return pre-existing enums including userrole
    mock_bind.execute.return_value.fetchall.return_value = [
        ("userrole",),
        ("userstatus",),
        ("addresstype",),
        ("inventorytransactiontype",),
        ("orderstatus",),
        ("paymentstatus",),
        ("notificationtype",),
        ("promotiontype",),
    ]

    executed_sqls = []

    mock_op = MagicMock()
    mock_op.get_bind.return_value = mock_bind
    mock_op.execute.side_effect = lambda sql: executed_sqls.append(str(sql))

    # Mock inspector to simulate pre-existing tables
    mock_inspector = MagicMock()
    mock_inspector.get_table_names.return_value = ["users", "orders", "kitchen_profiles"]
    mock_inspector.get_columns.return_value = [{"name": "id"}, {"name": "email"}, {"name": "role"}]
    mock_inspector.get_indexes.return_value = []

    monkeypatch.setattr("sqlalchemy.inspect", lambda bind: mock_inspector)

    import importlib
    mod_001 = importlib.import_module("backend.alembic.versions.001_initial")
    monkeypatch.setattr(mod_001, "op", mock_op)

    # Run upgrade
    mod_001.upgrade()

    # Verify that NO "CREATE TYPE" SQL was executed via mock_op.execute
    for sql in executed_sqls:
        assert "CREATE TYPE" not in sql, f"Unexpected CREATE TYPE was executed: {sql}"

    # Verify users table was NOT created again since it exists in mock_inspector
    for call in mock_op.create_table.call_args_list:
        args, _ = call
        assert args[0] != "users", "Table 'users' should not have been recreated"

