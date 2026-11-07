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
    # Normalize any legacy AI_GENERATED tags to MANUAL
    op.execute("UPDATE menu_items SET image_source = 'MANUAL' WHERE image_source = 'AI_GENERATED'")
    op.drop_column('menu_items', 'ai_image_prompt')
    op.drop_column('menu_items', 'ai_image_url')


def downgrade() -> None:
    op.add_column('menu_items', sa.Column('ai_image_url', sa.String(500), nullable=True))
    op.add_column('menu_items', sa.Column('ai_image_prompt', sa.Text(), nullable=True))
