"""add stock_loja and stock_deposito to inventory_items

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-05-05 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'l2m3n4o5p6q7'
down_revision = 'k1l2m3n4o5p6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('inventory_items', sa.Column('stock_loja', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('inventory_items', sa.Column('stock_deposito', sa.Integer(), nullable=False, server_default='0'))
    # Existing stock goes to loja (store) — preserves current behavior
    op.execute("UPDATE inventory_items SET stock_loja = current_stock")


def downgrade():
    op.drop_column('inventory_items', 'stock_deposito')
    op.drop_column('inventory_items', 'stock_loja')
