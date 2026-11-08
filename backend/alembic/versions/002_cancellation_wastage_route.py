"""Migration 002: Add cancellation wastage and route snapshot columns.

Revision ID: 002_cancellation_wastage_route
Revises: 001_initial
Create Date: 2026-10-06 15:10:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '002_cancellation_wastage_route'
down_revision: Union[str, None] = '001_initial'
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

    # 1. Order table columns for address snapshot and coordinates
    if 'orders' in tables:
        order_cols = {c['name'] for c in inspector.get_columns('orders')}
        if 'delivery_address_text' not in order_cols:
            op.add_column('orders', sa.Column('delivery_address_text', sa.String(500), nullable=True))
        if 'delivery_address_snapshot' not in order_cols:
            op.add_column('orders', sa.Column('delivery_address_snapshot', sa.Text(), nullable=True))
        if 'delivery_latitude' not in order_cols:
            op.add_column('orders', sa.Column('delivery_latitude', sa.Float(), nullable=True))
        if 'delivery_longitude' not in order_cols:
            op.add_column('orders', sa.Column('delivery_longitude', sa.Float(), nullable=True))

    # 2. Waste records columns for automatic cancellation wastage and analytics
    if 'waste_records' in tables:
        waste_cols = {c['name'] for c in inspector.get_columns('waste_records')}
        waste_indexes = {idx['name'] for idx in inspector.get_indexes('waste_records')}
        is_sqlite = bind.dialect.name == 'sqlite'
        try:
            op.alter_column('waste_records', 'ingredient_id', nullable=True)
        except Exception:
            pass
        if 'order_id' not in waste_cols:
            order_fk = [] if is_sqlite else [sa.ForeignKey('orders.id', ondelete='SET NULL')]
            op.add_column('waste_records', sa.Column('order_id', postgresql.UUID(as_uuid=True), *order_fk, nullable=True))
        if 'menu_item_id' not in waste_cols:
            menu_fk = [] if is_sqlite else [sa.ForeignKey('menu_items.id', ondelete='SET NULL')]
            op.add_column('waste_records', sa.Column('menu_item_id', postgresql.UUID(as_uuid=True), *menu_fk, nullable=True))
        if 'menu_item_name' not in waste_cols:
            op.add_column('waste_records', sa.Column('menu_item_name', sa.String(150), nullable=True))
        if 'portions_wasted' not in waste_cols:
            op.add_column('waste_records', sa.Column('portions_wasted', sa.Float(), nullable=True, server_default='1.0'))
        if 'estimated_cost' not in waste_cols:
            op.add_column('waste_records', sa.Column('estimated_cost', sa.Float(), nullable=False, server_default='0.0'))
        if 'source_event' not in waste_cols:
            op.add_column('waste_records', sa.Column('source_event', sa.String(50), nullable=True, server_default='MANUAL'))
        if 'unit' not in waste_cols:
            op.add_column('waste_records', sa.Column('unit', sa.String(20), nullable=True, server_default='kg'))
        if 'recorded_by' not in waste_cols:
            op.add_column('waste_records', sa.Column('recorded_by', sa.String(100), nullable=True, server_default='SYSTEM'))
        current_cols = {c['name'] for c in inspector.get_columns('waste_records')}
        if 'order_id' in current_cols and 'ix_waste_records_order_id' not in waste_indexes:
            op.create_index('ix_waste_records_order_id', 'waste_records', ['order_id'])
        if 'menu_item_id' in current_cols and 'ix_waste_records_menu_item_id' not in waste_indexes:
            op.create_index('ix_waste_records_menu_item_id', 'waste_records', ['menu_item_id'])


def downgrade() -> None:
    bind = op.get_bind()
    try:
        inspector = sa.inspect(bind)
        tables = set(inspector.get_table_names())
    except Exception:
        inspector = None
        tables = set()

    if 'waste_records' in tables:
        waste_cols = {c['name'] for c in inspector.get_columns('waste_records')}
        waste_indexes = {idx['name'] for idx in inspector.get_indexes('waste_records')}
        if 'ix_waste_records_menu_item_id' in waste_indexes:
            op.drop_index('ix_waste_records_menu_item_id', table_name='waste_records')
        if 'ix_waste_records_order_id' in waste_indexes:
            op.drop_index('ix_waste_records_order_id', table_name='waste_records')
        for col in ['recorded_by', 'unit', 'source_event', 'estimated_cost', 'portions_wasted', 'menu_item_name', 'menu_item_id', 'order_id']:
            if col in waste_cols:
                op.drop_column('waste_records', col)
        try:
            op.alter_column('waste_records', 'ingredient_id', nullable=False)
        except Exception:
            pass

    if 'orders' in tables:
        order_cols = {c['name'] for c in inspector.get_columns('orders')}
        for col in ['delivery_longitude', 'delivery_latitude', 'delivery_address_snapshot', 'delivery_address_text']:
            if col in order_cols:
                op.drop_column('orders', col)
