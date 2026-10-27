"""Read-only daily diagnostics history and indexed recent-metadata windows."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = 'p8e9f0a1b2c3'
down_revision = 'o7d8e9f0a1b2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('quality_config', sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('enabled', sa.Boolean(), nullable=False), sa.Column('ai_enabled', sa.Boolean(), nullable=False),
        sa.Column('local_time', sa.String(5), nullable=False), sa.Column('first_run_on', sa.Date(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False), sa.Column('ai_reserved_on', sa.Date()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_by', UUID(as_uuid=True), sa.ForeignKey('usuarios.id')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_table('quality_runs', sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('request_id', UUID(as_uuid=True), unique=True),
        sa.Column('requested_by', UUID(as_uuid=True), sa.ForeignKey('usuarios.id')),
        sa.Column('run_day', sa.Date(), nullable=False), sa.Column('kind', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), nullable=False), sa.Column('lease_token', sa.String(36)),
        sa.Column('lease_until', sa.DateTime(timezone=True)), sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False), sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True)), sa.Column('counters', sa.JSON(), nullable=False),
        sa.Column('coverage', sa.JSON(), nullable=False), sa.Column('findings', sa.JSON(), nullable=False),
        sa.Column('summary', sa.Text()), sa.Column('ai_summary', sa.Text()), sa.Column('ai_attempted', sa.Boolean(), nullable=False),
        sa.Column('ai_status', sa.String(30), nullable=False), sa.Column('provider', sa.String(40)),
        sa.Column('provider_calls', sa.Integer(), nullable=False), sa.Column('input_tokens', sa.Integer(), nullable=False),
        sa.Column('output_tokens', sa.Integer(), nullable=False), sa.Column('error_category', sa.String(100)))
    op.create_index('uq_quality_run_daily', 'quality_runs', ['run_day', 'kind'], unique=True,
                    postgresql_where=sa.text("kind = 'daily'"), sqlite_where=sa.text("kind = 'daily'"))
    op.create_index('ix_quality_runs_created', 'quality_runs', ['created_at', 'id'])


def downgrade():
    raise RuntimeError('Preserve quality reports and audit evidence; use a forward migration.')
