"""Migration 007: Add unit_cost field to ingredients table.

Revision ID: 007_add_ingredient_unit_cost
Revises: 006_fssai_food_licenses
Create Date: 2026-10-25 14:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '007_add_ingredient_unit_cost'
down_revision: Union[str, None] = '006_fssai_food_licenses'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    try:
        inspector = sa.inspect(bind)
        tables = set(inspector.get_table_names())
    except Exception:
        inspector = None
        tables = set()

    if 'ingredients' in tables:
        columns = {c['name'] for c in inspector.get_columns('ingredients')}
        if 'unit_cost' not in columns:
            op.add_column('ingredients', sa.Column('unit_cost', sa.Float(), nullable=True))
    elif inspector is None:
        op.add_column('ingredients', sa.Column('unit_cost', sa.Float(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    try:
        inspector = sa.inspect(bind)
        tables = set(inspector.get_table_names())
    except Exception:
        inspector = None
        tables = set()

    if 'ingredients' in tables:
        columns = {c['name'] for c in inspector.get_columns('ingredients')}
        if 'unit_cost' in columns:
            op.drop_column('ingredients', 'unit_cost')
    elif inspector is None:
        op.drop_column('ingredients', 'unit_cost')
