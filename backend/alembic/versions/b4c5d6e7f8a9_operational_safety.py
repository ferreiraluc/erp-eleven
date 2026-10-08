"""Shared login throttles and daily scheduler completion records."""
from alembic import op
import sqlalchemy as sa

revision = 'b4c5d6e7f8a9'
down_revision = 'a3b4c5d6e7f8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('login_throttles', sa.Column('bucket', sa.String(64), primary_key=True),
                    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
                    sa.Column('attempts', sa.Integer(), nullable=False))
    op.create_index('ix_login_throttles_started_at', 'login_throttles', ['started_at'])
    op.create_table('scheduled_runs', sa.Column('key', sa.String(80), primary_key=True),
                    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=False))


def downgrade():
    raise RuntimeError('Preserve os controles de autenticação e agendamento; use migração explícita.')
