"""Persist bounded print-agent diagnostics without changing existing jobs."""
from alembic import op
import sqlalchemy as sa

revision = 'g9b0c1d2e3f4'
down_revision = 'f8a9b0c1d2e3'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('print_jobs', sa.Column('diagnostic', sa.JSON(), nullable=True))


def downgrade():
    raise RuntimeError('Preserve o histórico de diagnósticos; reversão exige revisão explícita.')
