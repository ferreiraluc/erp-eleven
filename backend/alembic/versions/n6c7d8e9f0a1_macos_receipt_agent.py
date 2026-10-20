"""Opt-in macOS tickets; preserve all Windows devices and existing jobs."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = 'n6c7d8e9f0a1'
down_revision = 'm5b6c7d8e9f0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('print_devices', sa.Column('driver', sa.String(20), nullable=False, server_default='windows'))
    op.add_column('print_jobs', sa.Column('claim_key', UUID(as_uuid=True), nullable=True))
    op.create_index('uq_print_jobs_claim_key', 'print_jobs', ['claim_key'], unique=True)


def downgrade():
    raise RuntimeError('Preserve dispositivos, claims e histórico de impressão.')
