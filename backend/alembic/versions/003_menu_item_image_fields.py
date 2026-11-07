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
    op.add_column('menu_items', sa.Column('image_source', sa.String(30), nullable=False, server_default='MANUAL'))
    op.add_column('menu_items', sa.Column('manual_image_url', sa.String(500), nullable=True))
    op.add_column('menu_items', sa.Column('ai_image_url', sa.String(500), nullable=True))
    op.add_column('menu_items', sa.Column('ai_image_prompt', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('menu_items', 'ai_image_prompt')
    op.drop_column('menu_items', 'ai_image_url')
    op.drop_column('menu_items', 'manual_image_url')
    op.drop_column('menu_items', 'image_source')
