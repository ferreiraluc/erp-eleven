"""Durable recovery of interrupted freight requests; never backfill a purchase."""
from alembic import op
import sqlalchemy as sa

revision = 'c9d0e1f2a3b4'
down_revision = 'b8c9d0e1f2a3'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('freight_orders', sa.Column('error_category', sa.String(24)))
    op.add_column('freight_orders', sa.Column('recovery_kind', sa.String(24)))
    op.add_column('freight_orders', sa.Column('recovery_attempts', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('freight_orders', sa.Column('recovery_check_at', sa.DateTime(timezone=True)))
    op.create_index('ix_freight_orders_recovery_check_at', 'freight_orders', ['recovery_check_at'])


def downgrade():
    raise RuntimeError('Preserve as solicitações de recuperação; downgrade exige plano explícito.')
