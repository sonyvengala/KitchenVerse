"""Migration 004: Add cancellation_requests table for admin-assisted READY order cancellations.

Revision ID: 004_cancellation_requests
Revises: 003_menu_item_image_fields
Create Date: 2026-10-07 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

from sqlalchemy.dialects import postgresql

revision: str = '004_cancellation_requests'
down_revision: Union[str, None] = '003_menu_item_image_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'cancellation_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('order_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('kitchen_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('kitchen_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('customer_note', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='PENDING'),  # PENDING, APPROVED, REJECTED
        sa.Column('admin_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('admin_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_cancellation_requests_order_id', 'cancellation_requests', ['order_id'])
    op.create_index('ix_cancellation_requests_customer_id', 'cancellation_requests', ['customer_id'])
    op.create_index('ix_cancellation_requests_kitchen_id', 'cancellation_requests', ['kitchen_id'])
    op.create_index('ix_cancellation_requests_status', 'cancellation_requests', ['status'])


def downgrade() -> None:
    op.drop_index('ix_cancellation_requests_status', table_name='cancellation_requests')
    op.drop_index('ix_cancellation_requests_kitchen_id', table_name='cancellation_requests')
    op.drop_index('ix_cancellation_requests_customer_id', table_name='cancellation_requests')
    op.drop_index('ix_cancellation_requests_order_id', table_name='cancellation_requests')
    op.drop_table('cancellation_requests')
