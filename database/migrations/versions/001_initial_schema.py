"""001_initial_schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-10-03 15:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. roles
    op.create_table(
        'roles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_roles_id'), 'roles', ['id'], unique=False)
    op.create_index(op.f('ix_roles_name'), 'roles', ['name'], unique=True)

    # 2. users
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=150), nullable=False),
        sa.Column('phone_number', sa.String(length=30), nullable=True),
        sa.Column('role', sa.Enum('CUSTOMER', 'KITCHEN_OWNER', 'ADMIN', name='userrole'), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_verified', sa.Boolean(), nullable=False),
        sa.Column('verification_token', sa.String(length=255), nullable=True),
        sa.Column('password_reset_token', sa.String(length=255), nullable=True),
        sa.Column('password_reset_expires', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_role'), 'users', ['role'], unique=False)

    # 3. customer_profiles
    op.create_table(
        'customer_profiles',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('dietary_preferences', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )

    # 4. kitchen_profiles
    op.create_table(
        'kitchen_profiles',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('center_id', sa.Integer(), nullable=True),
        sa.Column('kitchen_name', sa.String(length=150), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('address', sa.String(length=255), nullable=False),
        sa.Column('city', sa.String(length=100), nullable=False),
        sa.Column('phone', sa.String(length=30), nullable=True),
        sa.Column('is_open', sa.Boolean(), nullable=False),
        sa.Column('is_approved', sa.Boolean(), nullable=False),
        sa.Column('rating', sa.Float(), nullable=False),
        sa.Column('rating_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    op.create_index(op.f('ix_kitchen_profiles_center_id'), 'kitchen_profiles', ['center_id'], unique=False)
    op.create_index(op.f('ix_kitchen_profiles_kitchen_name'), 'kitchen_profiles', ['kitchen_name'], unique=False)

    # 5. addresses
    op.create_table(
        'addresses',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('address_line1', sa.String(length=255), nullable=False),
        sa.Column('address_line2', sa.String(length=255), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=False),
        sa.Column('state', sa.String(length=100), nullable=False),
        sa.Column('postal_code', sa.String(length=20), nullable=False),
        sa.Column('landmark', sa.String(length=150), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_addresses_user_id'), 'addresses', ['user_id'], unique=False)

    # 6. user_sessions
    op.create_table(
        'user_sessions',
        sa.Column('session_id', sa.String(length=128), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_revoked', sa.Boolean(), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('session_id')
    )
    op.create_index(op.f('ix_user_sessions_expires_at'), 'user_sessions', ['expires_at'], unique=False)
    op.create_index(op.f('ix_user_sessions_session_id'), 'user_sessions', ['session_id'], unique=False)
    op.create_index(op.f('ix_user_sessions_user_id'), 'user_sessions', ['user_id'], unique=False)

    # 7. menu_items
    op.create_table(
        'menu_items',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('kitchen_id', sa.String(length=36), nullable=False),
        sa.Column('meal_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('cuisine', sa.String(length=50), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('is_available', sa.Boolean(), nullable=False),
        sa.Column('is_veg', sa.Boolean(), nullable=False),
        sa.Column('image_url', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['kitchen_id'], ['kitchen_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_menu_items_category'), 'menu_items', ['category'], unique=False)
    op.create_index(op.f('ix_menu_items_cuisine'), 'menu_items', ['cuisine'], unique=False)
    op.create_index(op.f('ix_menu_items_kitchen_id'), 'menu_items', ['kitchen_id'], unique=False)
    op.create_index(op.f('ix_menu_items_meal_id'), 'menu_items', ['meal_id'], unique=False)
    op.create_index(op.f('ix_menu_items_name'), 'menu_items', ['name'], unique=False)

    # 8. ingredients
    op.create_table(
        'ingredients',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('kitchen_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('unit', sa.String(length=20), nullable=False),
        sa.Column('current_stock', sa.Float(), nullable=False),
        sa.Column('minimum_stock_threshold', sa.Float(), nullable=False),
        sa.Column('reorder_quantity', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['kitchen_id'], ['kitchen_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('kitchen_id', 'name', name='uq_kitchen_ingredient_name')
    )
    op.create_index(op.f('ix_ingredients_kitchen_id'), 'ingredients', ['kitchen_id'], unique=False)
    op.create_index(op.f('ix_ingredients_name'), 'ingredients', ['name'], unique=False)

    # 9. menu_item_ingredients
    op.create_table(
        'menu_item_ingredients',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('menu_item_id', sa.String(length=36), nullable=False),
        sa.Column('ingredient_id', sa.String(length=36), nullable=False),
        sa.Column('quantity_required', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['ingredient_id'], ['ingredients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['menu_item_id'], ['menu_items.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('menu_item_id', 'ingredient_id', name='uq_menu_ingredient')
    )
    op.create_index(op.f('ix_menu_item_ingredients_ingredient_id'), 'menu_item_ingredients', ['ingredient_id'], unique=False)
    op.create_index(op.f('ix_menu_item_ingredients_menu_item_id'), 'menu_item_ingredients', ['menu_item_id'], unique=False)

    # 10. inventory
    op.create_table(
        'inventory',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('kitchen_id', sa.String(length=36), nullable=False),
        sa.Column('ingredient_id', sa.String(length=36), nullable=False),
        sa.Column('batch_number', sa.String(length=50), nullable=True),
        sa.Column('expiry_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=20), nullable=False),
        sa.Column('status', sa.Enum('AVAILABLE', 'LOW_STOCK', 'EXPIRED', name='inventorystatus'), nullable=False),
        sa.Column('last_updated', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['ingredient_id'], ['ingredients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['kitchen_id'], ['kitchen_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('kitchen_id', 'ingredient_id', name='uq_kitchen_ingredient_inventory')
    )
    op.create_index(op.f('ix_inventory_ingredient_id'), 'inventory', ['ingredient_id'], unique=False)
    op.create_index(op.f('ix_inventory_kitchen_id'), 'inventory', ['kitchen_id'], unique=False)
    op.create_index(op.f('ix_inventory_status'), 'inventory', ['status'], unique=False)

    # 11. inventory_transactions
    op.create_table(
        'inventory_transactions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('kitchen_id', sa.String(length=36), nullable=False),
        sa.Column('ingredient_id', sa.String(length=36), nullable=False),
        sa.Column('transaction_type', sa.Enum('INWARD', 'OUTWARD_ORDER', 'ADJUSTMENT', 'WASTE', name='inventorytransactiontype'), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('balance_after', sa.Float(), nullable=False),
        sa.Column('reference_order_id', sa.String(length=36), nullable=True),
        sa.Column('reason', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['ingredient_id'], ['ingredients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['kitchen_id'], ['kitchen_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_inventory_transactions_created_at'), 'inventory_transactions', ['created_at'], unique=False)
    op.create_index(op.f('ix_inventory_transactions_ingredient_id'), 'inventory_transactions', ['ingredient_id'], unique=False)
    op.create_index(op.f('ix_inventory_transactions_kitchen_id'), 'inventory_transactions', ['kitchen_id'], unique=False)
    op.create_index(op.f('ix_inventory_transactions_reference_order_id'), 'inventory_transactions', ['reference_order_id'], unique=False)
    op.create_index(op.f('ix_inventory_transactions_transaction_type'), 'inventory_transactions', ['transaction_type'], unique=False)

    # 12. purchases
    op.create_table(
        'purchases',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('kitchen_id', sa.String(length=36), nullable=False),
        sa.Column('ingredient_id', sa.String(length=36), nullable=False),
        sa.Column('supplier_name', sa.String(length=150), nullable=False),
        sa.Column('invoice_number', sa.String(length=100), nullable=True),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=20), nullable=False),
        sa.Column('unit_cost', sa.Float(), nullable=False),
        sa.Column('total_cost', sa.Float(), nullable=False),
        sa.Column('purchase_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['ingredient_id'], ['ingredients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['kitchen_id'], ['kitchen_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_purchases_ingredient_id'), 'purchases', ['ingredient_id'], unique=False)
    op.create_index(op.f('ix_purchases_kitchen_id'), 'purchases', ['kitchen_id'], unique=False)

    # 13. waste_records
    op.create_table(
        'waste_records',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('kitchen_id', sa.String(length=36), nullable=False),
        sa.Column('ingredient_id', sa.String(length=36), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=20), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('recorded_by', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['ingredient_id'], ['ingredients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['kitchen_id'], ['kitchen_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_waste_records_created_at'), 'waste_records', ['created_at'], unique=False)
    op.create_index(op.f('ix_waste_records_ingredient_id'), 'waste_records', ['ingredient_id'], unique=False)
    op.create_index(op.f('ix_waste_records_kitchen_id'), 'waste_records', ['kitchen_id'], unique=False)

    # 14. orders
    op.create_table(
        'orders',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('order_number', sa.String(length=32), nullable=False),
        sa.Column('customer_id', sa.String(length=36), nullable=False),
        sa.Column('kitchen_id', sa.String(length=36), nullable=False),
        sa.Column('delivery_address_id', sa.String(length=36), nullable=True),
        sa.Column('status', sa.Enum('ORDER_PLACED', 'PAYMENT_CONFIRMED', 'KITCHEN_ACCEPTED', 'PREPARING', 'READY', 'OUT_FOR_DELIVERY', 'DELIVERED', 'CANCELLED', 'REJECTED', 'REFUNDED', name='orderstatus'), nullable=False),
        sa.Column('subtotal', sa.Float(), nullable=False),
        sa.Column('tax', sa.Float(), nullable=False),
        sa.Column('delivery_fee', sa.Float(), nullable=False),
        sa.Column('total_amount', sa.Float(), nullable=False),
        sa.Column('payment_status', sa.Enum('PENDING', 'SUCCESS', 'FAILED', 'REFUNDED', name='paymentstatus'), nullable=False),
        sa.Column('special_instructions', sa.Text(), nullable=True),
        sa.Column('rejection_reason', sa.String(length=255), nullable=True),
        sa.Column('cancellation_reason', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['delivery_address_id'], ['addresses.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['kitchen_id'], ['kitchen_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_orders_created_at'), 'orders', ['created_at'], unique=False)
    op.create_index(op.f('ix_orders_customer_id'), 'orders', ['customer_id'], unique=False)
    op.create_index(op.f('ix_orders_kitchen_id'), 'orders', ['kitchen_id'], unique=False)
    op.create_index(op.f('ix_orders_order_number'), 'orders', ['order_number'], unique=True)
    op.create_index(op.f('ix_orders_payment_status'), 'orders', ['payment_status'], unique=False)
    op.create_index(op.f('ix_orders_status'), 'orders', ['status'], unique=False)

    # 15. order_items
    op.create_table(
        'order_items',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('order_id', sa.String(length=36), nullable=False),
        sa.Column('menu_item_id', sa.String(length=36), nullable=True),
        sa.Column('item_name', sa.String(length=150), nullable=False),
        sa.Column('unit_price', sa.Float(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('subtotal', sa.Float(), nullable=False),
        sa.Column('special_requests', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['menu_item_id'], ['menu_items.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_order_items_menu_item_id'), 'order_items', ['menu_item_id'], unique=False)
    op.create_index(op.f('ix_order_items_order_id'), 'order_items', ['order_id'], unique=False)

    # 16. payments
    op.create_table(
        'payments',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('order_id', sa.String(length=36), nullable=False),
        sa.Column('payment_provider', sa.String(length=50), nullable=False),
        sa.Column('transaction_reference', sa.String(length=100), nullable=True),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(length=10), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'SUCCESS', 'FAILED', 'REFUNDED', name='paymentstatus'), nullable=False),
        sa.Column('provider_response_payload', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_payments_order_id'), 'payments', ['order_id'], unique=False)
    op.create_index(op.f('ix_payments_status'), 'payments', ['status'], unique=False)
    op.create_index(op.f('ix_payments_transaction_reference'), 'payments', ['transaction_reference'], unique=True)

    # 17. reviews
    op.create_table(
        'reviews',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('order_id', sa.String(length=36), nullable=False),
        sa.Column('customer_id', sa.String(length=36), nullable=False),
        sa.Column('kitchen_id', sa.String(length=36), nullable=False),
        sa.Column('menu_item_id', sa.String(length=36), nullable=True),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('rating >= 1 AND rating <= 5', name='check_rating_range'),
        sa.ForeignKeyConstraint(['customer_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['kitchen_id'], ['kitchen_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['menu_item_id'], ['menu_items.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_reviews_customer_id'), 'reviews', ['customer_id'], unique=False)
    op.create_index(op.f('ix_reviews_kitchen_id'), 'reviews', ['kitchen_id'], unique=False)
    op.create_index(op.f('ix_reviews_order_id'), 'reviews', ['order_id'], unique=False)

    # 18. favorites
    op.create_table(
        'favorites',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('customer_id', sa.String(length=36), nullable=False),
        sa.Column('kitchen_id', sa.String(length=36), nullable=True),
        sa.Column('menu_item_id', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['kitchen_id'], ['kitchen_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['menu_item_id'], ['menu_items.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_favorites_customer_id'), 'favorites', ['customer_id'], unique=False)
    op.create_index(op.f('ix_favorites_kitchen_id'), 'favorites', ['kitchen_id'], unique=False)
    op.create_index(op.f('ix_favorites_menu_item_id'), 'favorites', ['menu_item_id'], unique=False)

    # 19. notifications
    op.create_table(
        'notifications',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('is_read', sa.Boolean(), nullable=False),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notifications_created_at'), 'notifications', ['created_at'], unique=False)
    op.create_index(op.f('ix_notifications_event_type'), 'notifications', ['event_type'], unique=False)
    op.create_index(op.f('ix_notifications_is_read'), 'notifications', ['is_read'], unique=False)
    op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)

    # 20. promotions
    op.create_table(
        'promotions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=150), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('discount_percentage', sa.Float(), nullable=False),
        sa.Column('discount_amount', sa.Float(), nullable=False),
        sa.Column('minimum_order_amount', sa.Float(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_promotions_code'), 'promotions', ['code'], unique=True)

    # 21. model_versions
    op.create_table(
        'model_versions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('model_name', sa.String(length=100), nullable=False),
        sa.Column('version', sa.String(length=50), nullable=False),
        sa.Column('training_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('training_start_week', sa.Integer(), nullable=True),
        sa.Column('training_end_week', sa.Integer(), nullable=True),
        sa.Column('validation_period', sa.String(length=100), nullable=True),
        sa.Column('metrics_json', sa.Text(), nullable=False),
        sa.Column('feature_config_json', sa.Text(), nullable=True),
        sa.Column('artifact_path', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_model_versions_model_name'), 'model_versions', ['model_name'], unique=False)
    op.create_index(op.f('ix_model_versions_version'), 'model_versions', ['version'], unique=False)

    # 22. demand_predictions
    op.create_table(
        'demand_predictions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('model_version_id', sa.String(length=36), nullable=False),
        sa.Column('center_id', sa.Integer(), nullable=False),
        sa.Column('meal_id', sa.Integer(), nullable=False),
        sa.Column('prediction_period', sa.String(length=50), nullable=False),
        sa.Column('predicted_demand', sa.Float(), nullable=False),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['model_version_id'], ['model_versions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_demand_predictions_center_id'), 'demand_predictions', ['center_id'], unique=False)
    op.create_index(op.f('ix_demand_predictions_meal_id'), 'demand_predictions', ['meal_id'], unique=False)
    op.create_index(op.f('ix_demand_predictions_model_version_id'), 'demand_predictions', ['model_version_id'], unique=False)
    op.create_index(op.f('ix_demand_predictions_prediction_period'), 'demand_predictions', ['prediction_period'], unique=False)

    # 23. audit_logs
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('entity_name', sa.String(length=100), nullable=False),
        sa.Column('entity_id', sa.String(length=100), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=255), nullable=True),
        sa.Column('details_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_created_at'), 'audit_logs', ['created_at'], unique=False)
    op.create_index(op.f('ix_audit_logs_entity_id'), 'audit_logs', ['entity_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_entity_name'), 'audit_logs', ['entity_name'], unique=False)
    op.create_index(op.f('ix_audit_logs_user_id'), 'audit_logs', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('demand_predictions')
    op.drop_table('model_versions')
    op.drop_table('promotions')
    op.drop_table('notifications')
    op.drop_table('favorites')
    op.drop_table('reviews')
    op.drop_table('payments')
    op.drop_table('order_items')
    op.drop_table('orders')
    op.drop_table('waste_records')
    op.drop_table('purchases')
    op.drop_table('inventory_transactions')
    op.drop_table('inventory')
    op.drop_table('menu_item_ingredients')
    op.drop_table('ingredients')
    op.drop_table('menu_items')
    op.drop_table('user_sessions')
    op.drop_table('addresses')
    op.drop_table('kitchen_profiles')
    op.drop_table('customer_profiles')
    op.drop_table('users')
    op.drop_table('roles')
