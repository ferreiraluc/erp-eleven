"""Record store balances on new movements without inferring legacy history."""
from alembic import op
import sqlalchemy as sa

revision = 'w5f6a7b8c9d0'
down_revision = 'v4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade():
    # Existing before/after quantities describe combined stock. They cannot be
    # copied into store balances, especially for depot moves and repaired totals.
    op.add_column('stock_movements', sa.Column('stock_loja_before', sa.Integer(), nullable=True))
    op.add_column('stock_movements', sa.Column('stock_loja_after', sa.Integer(), nullable=True))


def downgrade():
    raise RuntimeError('Preserve recorded store balances; use a forward migration.')
