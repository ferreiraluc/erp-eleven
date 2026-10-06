"""Persist vendor BI identity and address reconciliation review state."""
from alembic import op
import sqlalchemy as sa

revision = 'd0e1f2a3b4c5'
down_revision = 'c9d0e1f2a3b4'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('vendedores', sa.Column('sales_seller', sa.String(100)))
    op.create_unique_constraint('uq_vendedores_sales_seller', 'vendedores', ['sales_seller'])
    op.add_column('saved_addresses', sa.Column('customer_link_review', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('saved_addresses', sa.Column('customer_link_reason', sa.String(40)))


def downgrade():
    raise RuntimeError('Preserve os vínculos de identidade; downgrade exige plano explícito.')
