"""Migration 005: Remove AI menu image fields (ai_image_url, ai_image_prompt).

Revision ID: 005_remove_ai_menu_image_fields
Revises: 004_cancellation_requests
Create Date: 2026-10-08 11:45:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '005_remove_ai_menu_image_fields'
down_revision: Union[str, None] = '004_cancellation_requests'
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
        if 'image_source' in cols:
            op.execute("UPDATE menu_items SET image_source = 'MANUAL' WHERE image_source = 'AI_GENERATED'")
        if 'ai_image_prompt' in cols:
            op.drop_column('menu_items', 'ai_image_prompt')
        if 'ai_image_url' in cols:
            op.drop_column('menu_items', 'ai_image_url')
    elif inspector is None:
        op.execute("UPDATE menu_items SET image_source = 'MANUAL' WHERE image_source = 'AI_GENERATED'")
        op.drop_column('menu_items', 'ai_image_prompt')
        op.drop_column('menu_items', 'ai_image_url')


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
        if 'ai_image_url' not in cols:
            op.add_column('menu_items', sa.Column('ai_image_url', sa.String(500), nullable=True))
        if 'ai_image_prompt' not in cols:
            op.add_column('menu_items', sa.Column('ai_image_prompt', sa.Text(), nullable=True))
    elif inspector is None:
        op.add_column('menu_items', sa.Column('ai_image_url', sa.String(500), nullable=True))
        op.add_column('menu_items', sa.Column('ai_image_prompt', sa.Text(), nullable=True))
