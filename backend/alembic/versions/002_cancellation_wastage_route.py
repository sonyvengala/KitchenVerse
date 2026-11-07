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
    # 1. Order table columns for address snapshot and coordinates
    op.add_column('orders', sa.Column('delivery_address_text', sa.String(500), nullable=True))
    op.add_column('orders', sa.Column('delivery_address_snapshot', sa.Text(), nullable=True))
    op.add_column('orders', sa.Column('delivery_latitude', sa.Float(), nullable=True))
    op.add_column('orders', sa.Column('delivery_longitude', sa.Float(), nullable=True))

    # 2. Waste records columns for automatic cancellation wastage and analytics
    op.alter_column('waste_records', 'ingredient_id', nullable=True)
    op.add_column('waste_records', sa.Column('order_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('orders.id', ondelete='SET NULL'), nullable=True))
    op.add_column('waste_records', sa.Column('menu_item_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('menu_items.id', ondelete='SET NULL'), nullable=True))
    op.add_column('waste_records', sa.Column('menu_item_name', sa.String(150), nullable=True))
    op.add_column('waste_records', sa.Column('portions_wasted', sa.Float(), nullable=True, server_default='1.0'))
    op.add_column('waste_records', sa.Column('estimated_cost', sa.Float(), nullable=False, server_default='0.0'))
    op.add_column('waste_records', sa.Column('source_event', sa.String(50), nullable=True, server_default='MANUAL'))
    op.add_column('waste_records', sa.Column('unit', sa.String(20), nullable=True, server_default='kg'))
    op.add_column('waste_records', sa.Column('recorded_by', sa.String(100), nullable=True, server_default='SYSTEM'))
    op.create_index('ix_waste_records_order_id', 'waste_records', ['order_id'])
    op.create_index('ix_waste_records_menu_item_id', 'waste_records', ['menu_item_id'])


def downgrade() -> None:
    op.drop_index('ix_waste_records_menu_item_id', table_name='waste_records')
    op.drop_index('ix_waste_records_order_id', table_name='waste_records')
    op.drop_column('waste_records', 'recorded_by')
    op.drop_column('waste_records', 'unit')
    op.drop_column('waste_records', 'source_event')
    op.drop_column('waste_records', 'estimated_cost')
    op.drop_column('waste_records', 'portions_wasted')
    op.drop_column('waste_records', 'menu_item_name')
    op.drop_column('waste_records', 'menu_item_id')
    op.drop_column('waste_records', 'order_id')
    op.alter_column('waste_records', 'ingredient_id', nullable=False)

    op.drop_column('orders', 'delivery_longitude')
    op.drop_column('orders', 'delivery_latitude')
    op.drop_column('orders', 'delivery_address_snapshot')
    op.drop_column('orders', 'delivery_address_text')
