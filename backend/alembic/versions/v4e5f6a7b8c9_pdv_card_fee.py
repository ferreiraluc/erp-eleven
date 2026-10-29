"""Separate the terminal charge from the merchandise payment; preserve history."""
from alembic import op
import sqlalchemy as sa

revision = 'v4e5f6a7b8c9'
down_revision = 'u3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('pdv_payments', sa.Column('card_fee_gs', sa.Numeric(15, 2), nullable=False, server_default='0'))
    op.add_column('pdv_payments', sa.Column('card_fee_percent', sa.Numeric(5, 2), nullable=False, server_default='0'))


def downgrade():
    raise RuntimeError('Preserve recorded card charges; use a forward migration.')
