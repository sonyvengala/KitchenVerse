"""Migration 006: Add FSSAI Food Licenses and Document History tables.

Revision ID: 006_fssai_food_licenses
Revises: 005_remove_ai_menu_image_fields
Create Date: 2026-10-13 17:20:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '006_fssai_food_licenses'
down_revision: Union[str, None] = '005_remove_ai_menu_image_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create kitchen_licenses table
    op.create_table(
        'kitchen_licenses',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('kitchen_id', sa.String(length=36), nullable=False),
        sa.Column('license_number', sa.String(length=50), nullable=False),
        sa.Column('raw_license_number', sa.String(length=100), nullable=True),
        sa.Column('business_name', sa.String(length=200), nullable=False),
        sa.Column('issue_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expiry_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='PENDING_REVIEW'),
        sa.Column('verification_source', sa.String(length=50), nullable=False, server_default='MANUAL'),
        sa.Column('verified_by_user_id', sa.String(length=36), nullable=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('correction_reason', sa.Text(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('duplicate_flag', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('duplicate_details', sa.Text(), nullable=True),
        sa.Column('ocr_extracted_data', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['kitchen_id'], ['kitchen_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['verified_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('kitchen_id', name='uq_kitchen_licenses_kitchen_id')
    )
    op.create_index('ix_kitchen_licenses_license_number', 'kitchen_licenses', ['license_number'])
    op.create_index('ix_kitchen_licenses_status', 'kitchen_licenses', ['status'])
    op.create_index('ix_kitchen_licenses_expiry_date', 'kitchen_licenses', ['expiry_date'])
    op.create_index('ix_kitchen_licenses_duplicate_flag', 'kitchen_licenses', ['duplicate_flag'])

    # 2. Create kitchen_license_documents table
    op.create_table(
        'kitchen_license_documents',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('license_id', sa.String(length=36), nullable=False),
        sa.Column('file_path', sa.String(length=255), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=False),
        sa.Column('file_hash', sa.String(length=64), nullable=True),
        sa.Column('document_type', sa.String(length=50), nullable=False, server_default='INITIAL'),
        sa.Column('ocr_extracted_data', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['license_id'], ['kitchen_licenses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_kitchen_license_documents_license_id', 'kitchen_license_documents', ['license_id'])
    op.create_index('ix_kitchen_license_documents_file_hash', 'kitchen_license_documents', ['file_hash'])


def downgrade() -> None:
    op.drop_index('ix_kitchen_license_documents_file_hash', table_name='kitchen_license_documents')
    op.drop_index('ix_kitchen_license_documents_license_id', table_name='kitchen_license_documents')
    op.drop_table('kitchen_license_documents')
    op.drop_index('ix_kitchen_licenses_duplicate_flag', table_name='kitchen_licenses')
    op.drop_index('ix_kitchen_licenses_expiry_date', table_name='kitchen_licenses')
    op.drop_index('ix_kitchen_licenses_status', table_name='kitchen_licenses')
    op.drop_index('ix_kitchen_licenses_license_number', table_name='kitchen_licenses')
    op.drop_table('kitchen_licenses')
