"""add brand and group_key to inventory_items

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'f6a7b8c9d0e1'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('inventory_items', sa.Column('brand', sa.String(100), nullable=True))
    op.add_column('inventory_items', sa.Column('group_key', sa.String(100), nullable=True))
    op.create_index('ix_inventory_items_group_key', 'inventory_items', ['group_key'])


def downgrade() -> None:
    op.drop_index('ix_inventory_items_group_key', table_name='inventory_items')
    op.drop_column('inventory_items', 'group_key')
    op.drop_column('inventory_items', 'brand')
