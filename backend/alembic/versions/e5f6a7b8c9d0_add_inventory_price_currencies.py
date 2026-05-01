"""add cost_currency and sale_currency to inventory_items

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'inventory_items',
        sa.Column('cost_currency', sa.String(10), nullable=True, server_default='PYG')
    )
    op.add_column(
        'inventory_items',
        sa.Column('sale_currency', sa.String(10), nullable=True, server_default='PYG')
    )


def downgrade() -> None:
    op.drop_column('inventory_items', 'sale_currency')
    op.drop_column('inventory_items', 'cost_currency')
