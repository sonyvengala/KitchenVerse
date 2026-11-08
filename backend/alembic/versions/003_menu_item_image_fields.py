"""Migration 003: Add image_source, manual_image_url, ai_image_url, ai_image_prompt to menu_items.

Revision ID: 003_menu_item_image_fields
Revises: 002_cancellation_wastage_route
Create Date: 2026-10-06 20:20:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '003_menu_item_image_fields'
down_revision: Union[str, None] = '002_cancellation_wastage_route'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    try:
        inspector = sa.inspect(bind)
        table_names = set(inspector.get_table_names())
    except Exception:
        inspector = None
        table_names = set()

    if 'menu_items' in table_names:
        cols = {c['name'] for c in inspector.get_columns('menu_items')}
        if 'image_source' not in cols:
            op.add_column('menu_items', sa.Column('image_source', sa.String(30), nullable=False, server_default='MANUAL'))
        if 'manual_image_url' not in cols:
            op.add_column('menu_items', sa.Column('manual_image_url', sa.String(500), nullable=True))
        if 'ai_image_url' not in cols:
            op.add_column('menu_items', sa.Column('ai_image_url', sa.String(500), nullable=True))
        if 'ai_image_prompt' not in cols:
            op.add_column('menu_items', sa.Column('ai_image_prompt', sa.Text(), nullable=True))
    elif inspector is None:
        op.add_column('menu_items', sa.Column('image_source', sa.String(30), nullable=False, server_default='MANUAL'))
        op.add_column('menu_items', sa.Column('manual_image_url', sa.String(500), nullable=True))
        op.add_column('menu_items', sa.Column('ai_image_url', sa.String(500), nullable=True))
        op.add_column('menu_items', sa.Column('ai_image_prompt', sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    try:
        inspector = sa.inspect(bind)
        table_names = set(inspector.get_table_names())
    except Exception:
        inspector = None
        table_names = set()

    if 'menu_items' in table_names:
        cols = {c['name'] for c in inspector.get_columns('menu_items')}
        for col in ['ai_image_prompt', 'ai_image_url', 'manual_image_url', 'image_source']:
            if col in cols:
                op.drop_column('menu_items', col)
    elif inspector is None:
        for col in ['ai_image_prompt', 'ai_image_url', 'manual_image_url', 'image_source']:
            op.drop_column('menu_items', col)
