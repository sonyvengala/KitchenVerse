"""Initial migration - create all tables.

Revision ID: 001_initial
Revises: 
Create Date: 2026-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('first_name', sa.String(100), nullable=False),
        sa.Column('last_name', sa.String(100), nullable=False),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('role', sa.Enum('CUSTOMER', 'KITCHEN_OWNER', 'ADMIN', name='userrole'), nullable=False, server_default='CUSTOMER'),
        sa.Column('status', sa.Enum('ACTIVE', 'INACTIVE', 'SUSPENDED', 'PENDING_VERIFICATION', name='userstatus'), nullable=False, server_default='PENDING_VERIFICATION'),
        sa.Column('is_email_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_users_email_lower', 'users', ['email'])
    op.create_index('ix_users_role_status', 'users', ['role', 'status'])

    # Customer profiles
    op.create_table(
        'customer_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('loyalty_points', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_orders', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_spent', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('preferences', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    # Kitchen profiles
    op.create_table(
        'kitchen_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('kitchen_name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('cuisine_types', postgresql.JSON(), nullable=True),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('rating', sa.Float(), nullable=True),
        sa.Column('total_reviews', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('operating_hours', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    # Addresses
    op.create_table(
        'addresses',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('address_type', sa.Enum('HOME', 'WORK', 'OTHER', name='addresstype'), nullable=False, server_default='HOME'),
        sa.Column('street', sa.String(255), nullable=False),
        sa.Column('city', sa.String(100), nullable=False),
        sa.Column('state', sa.String(100), nullable=True),
        sa.Column('postal_code', sa.String(20), nullable=False),
        sa.Column('country', sa.String(100), nullable=False, server_default='US'),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    # Ingredients
    op.create_table(
        'ingredients',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), unique=True, nullable=False),
        sa.Column('unit', sa.String(50), nullable=False),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    # Menu items
    op.create_table(
        'menu_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('kitchen_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('kitchen_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('image_url', sa.String(500), nullable=True),
        sa.Column('is_available', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_vegetarian', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_vegan', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_gluten_free', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('preparation_time_minutes', sa.Integer(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_menu_items_kitchen_available', 'menu_items', ['kitchen_id', 'is_available'])

    # Menu item ingredients (join table)
    op.create_table(
        'menu_item_ingredients',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('menu_item_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('menu_items.id', ondelete='CASCADE'), nullable=False),
        sa.Column('ingredient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ingredients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('quantity_required', sa.Float(), nullable=False),
        sa.UniqueConstraint('menu_item_id', 'ingredient_id', name='uq_menu_item_ingredient'),
    )

    # Inventory
    op.create_table(
        'inventory',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('kitchen_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('kitchen_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('ingredient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ingredients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('quantity_on_hand', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('min_quantity', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('max_quantity', sa.Float(), nullable=True),
        sa.Column('unit_cost', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('last_restocked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.UniqueConstraint('kitchen_id', 'ingredient_id', name='uq_kitchen_ingredient'),
    )

    # Inventory transactions
    op.create_table(
        'inventory_transactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('inventory_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('inventory.id', ondelete='CASCADE'), nullable=False),
        sa.Column('transaction_type', sa.Enum('PURCHASE', 'USAGE', 'ADJUSTMENT', 'WASTE', 'RETURN', name='inventorytransactiontype'), nullable=False),
        sa.Column('quantity_change', sa.Float(), nullable=False),
        sa.Column('reason', sa.String(255), nullable=True),
        sa.Column('reference_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('performed_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    # Orders
    op.create_table(
        'orders',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('kitchen_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('kitchen_profiles.id', ondelete='SET NULL'), nullable=True),
        sa.Column('status', sa.Enum('PENDING', 'CONFIRMED', 'PREPARING', 'READY', 'OUT_FOR_DELIVERY', 'DELIVERED', 'CANCELLED', 'REFUNDED', name='orderstatus'), nullable=False, server_default='PENDING'),
        sa.Column('subtotal', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('tax_amount', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('delivery_fee', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('discount_amount', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('total_amount', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('delivery_address', postgresql.JSON(), nullable=True),
        sa.Column('special_instructions', sa.Text(), nullable=True),
        sa.Column('estimated_delivery_minutes', sa.Integer(), nullable=True),
        sa.Column('ordered_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_orders_customer_status', 'orders', ['customer_id', 'status'])
    op.create_index('ix_orders_kitchen_status', 'orders', ['kitchen_id', 'status'])

    # Order items
    op.create_table(
        'order_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('order_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False),
        sa.Column('menu_item_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('menu_items.id', ondelete='SET NULL'), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('unit_price', sa.Float(), nullable=False),
        sa.Column('total_price', sa.Float(), nullable=False),
        sa.Column('special_instructions', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    # Payments
    op.create_table(
        'payments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('order_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('orders.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'COMPLETED', 'FAILED', 'REFUNDED', name='paymentstatus'), nullable=False, server_default='PENDING'),
        sa.Column('payment_method', sa.String(50), nullable=True),
        sa.Column('transaction_id', sa.String(255), unique=True, nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    # Reviews
    op.create_table(
        'reviews',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('order_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('orders.id', ondelete='SET NULL'), nullable=True),
        sa.Column('kitchen_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('kitchen_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('is_visible', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.UniqueConstraint('user_id', 'order_id', name='uq_review_per_order'),
    )

    # Favorites
    op.create_table(
        'favorites',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('menu_item_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('menu_items.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.UniqueConstraint('user_id', 'menu_item_id', name='uq_favorite_per_user'),
    )

    # Notifications
    op.create_table(
        'notifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('notification_type', sa.Enum('ORDER_UPDATE', 'PROMOTION', 'SYSTEM', 'REVIEW_REQUEST', name='notificationtype'), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('data', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_notifications_user_read', 'notifications', ['user_id', 'is_read'])

    # Promotions
    op.create_table(
        'promotions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('kitchen_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('kitchen_profiles.id', ondelete='CASCADE'), nullable=True),
        sa.Column('code', sa.String(50), unique=True, nullable=False),
        sa.Column('promotion_type', sa.Enum('PERCENTAGE', 'FIXED_AMOUNT', 'FREE_DELIVERY', 'BUY_GET', name='promotiontype'), nullable=False),
        sa.Column('discount_value', sa.Float(), nullable=False),
        sa.Column('min_order_amount', sa.Float(), nullable=True),
        sa.Column('max_discount', sa.Float(), nullable=True),
        sa.Column('usage_limit', sa.Integer(), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    # Purchases
    op.create_table(
        'purchases',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('kitchen_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('kitchen_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('ingredient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ingredients.id', ondelete='SET NULL'), nullable=True),
        sa.Column('supplier_name', sa.String(255), nullable=True),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('unit_cost', sa.Float(), nullable=False),
        sa.Column('total_cost', sa.Float(), nullable=False),
        sa.Column('purchased_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    # Waste records
    op.create_table(
        'waste_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('kitchen_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('kitchen_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('ingredient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ingredients.id', ondelete='SET NULL'), nullable=True),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('reason', sa.String(255), nullable=True),
        sa.Column('cost', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    # Demand predictions
    op.create_table(
        'demand_predictions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('kitchen_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('kitchen_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('menu_item_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('menu_items.id', ondelete='SET NULL'), nullable=True),
        sa.Column('prediction_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('predicted_demand', sa.Float(), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('model_version', sa.String(50), nullable=True),
        sa.Column('features', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_demand_predictions_kitchen_date', 'demand_predictions', ['kitchen_id', 'prediction_date'])

    # Audit logs
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('resource_type', sa.String(100), nullable=True),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('details', postgresql.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_audit_logs_user_action', 'audit_logs', ['user_id', 'action'])
    op.create_index('ix_audit_logs_created', 'audit_logs', ['created_at'])


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('demand_predictions')
    op.drop_table('waste_records')
    op.drop_table('purchases')
    op.drop_table('promotions')
    op.drop_table('notifications')
    op.drop_table('favorites')
    op.drop_table('reviews')
    op.drop_table('payments')
    op.drop_table('order_items')
    op.drop_table('orders')
    op.drop_table('inventory_transactions')
    op.drop_table('inventory')
    op.drop_table('menu_item_ingredients')
    op.drop_table('menu_items')
    op.drop_table('ingredients')
    op.drop_table('addresses')
    op.drop_table('kitchen_profiles')
    op.drop_table('customer_profiles')
    op.drop_table('users')
