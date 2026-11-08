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
    bind = op.get_bind()
    try:
        inspector = sa.inspect(bind)
        tables = set(inspector.get_table_names())
    except Exception:
        inspector = None
        tables = set()

    if 'cancellation_requests' not in tables:
        op.create_table(
            'cancellation_requests',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('order_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False),
            sa.Column('customer_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('kitchen_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('kitchen_profiles.id', ondelete='CASCADE'), nullable=False),
            sa.Column('reason', sa.Text(), nullable=True),
            sa.Column('customer_note', sa.Text(), nullable=True),
            sa.Column('status', sa.String(20), nullable=False, server_default='PENDING'),
            sa.Column('admin_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('admin_note', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index('ix_cancellation_requests_order_id', 'cancellation_requests', ['order_id'])
        op.create_index('ix_cancellation_requests_customer_id', 'cancellation_requests', ['customer_id'])
        op.create_index('ix_cancellation_requests_kitchen_id', 'cancellation_requests', ['kitchen_id'])
        op.create_index('ix_cancellation_requests_status', 'cancellation_requests', ['status'])
    else:
        cols = {c['name'] for c in inspector.get_columns('cancellation_requests')}
        idxs = {i['name'] for i in inspector.get_indexes('cancellation_requests')}
        if 'order_id' in cols and 'ix_cancellation_requests_order_id' not in idxs:
            op.create_index('ix_cancellation_requests_order_id', 'cancellation_requests', ['order_id'])
        if 'customer_id' in cols and 'ix_cancellation_requests_customer_id' not in idxs:
            op.create_index('ix_cancellation_requests_customer_id', 'cancellation_requests', ['customer_id'])
        if 'kitchen_id' in cols and 'ix_cancellation_requests_kitchen_id' not in idxs:
            op.create_index('ix_cancellation_requests_kitchen_id', 'cancellation_requests', ['kitchen_id'])
        if 'status' in cols and 'ix_cancellation_requests_status' not in idxs:
            op.create_index('ix_cancellation_requests_status', 'cancellation_requests', ['status'])


def downgrade() -> None:
    bind = op.get_bind()
    try:
        inspector = sa.inspect(bind)
        table_names = set(inspector.get_table_names())
    except Exception:
        inspector = None
        table_names = set()

    if 'cancellation_requests' in table_names:
        idxs = {i['name'] for i in inspector.get_indexes('cancellation_requests')}
        for idx in ['ix_cancellation_requests_status', 'ix_cancellation_requests_kitchen_id', 'ix_cancellation_requests_customer_id', 'ix_cancellation_requests_order_id']:
            if idx in idxs:
                op.drop_index(idx, table_name='cancellation_requests')
        op.drop_table('cancellation_requests')
    elif inspector is None:
        op.drop_index('ix_cancellation_requests_status', table_name='cancellation_requests')
        op.drop_index('ix_cancellation_requests_kitchen_id', table_name='cancellation_requests')
        op.drop_index('ix_cancellation_requests_customer_id', table_name='cancellation_requests')
        op.drop_index('ix_cancellation_requests_order_id', table_name='cancellation_requests')
        op.drop_table('cancellation_requests')
