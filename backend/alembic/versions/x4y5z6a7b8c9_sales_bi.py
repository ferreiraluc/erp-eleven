"""Add isolated, read-only sales spreadsheet snapshots and synchronization state."""
from alembic import op
import sqlalchemy as sa

revision = 'x4y5z6a7b8c9'
down_revision = 'w3x4y5z6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('sales_bi_config',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('current_url', sa.String(2500), nullable=False),
        sa.Column('archive_url', sa.String(2500), nullable=False),
        sa.Column('archive_root', sa.String(1000), nullable=False),
        sa.Column('current_year', sa.Integer()), sa.Column('current_month', sa.Integer()),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        *[sa.Column(name, sa.DateTime(timezone=True)) for name in
          ['requested_at', 'started_at', 'finished_at', 'next_sync_at', 'lease_until']],
        sa.Column('lease_token', sa.String(36)), sa.Column('last_error', sa.String(500)))
    op.create_table('sales_bi_workbooks',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('kind', sa.String(16), nullable=False), sa.Column('filename', sa.String(300), nullable=False),
        sa.Column('year', sa.Integer()), sa.Column('month', sa.Integer()),
        sa.Column('remote_version', sa.String(200)), sa.Column('content_hash', sa.String(64)),
        sa.Column('parser_version', sa.Integer()), sa.Column('snapshot', sa.JSON()),
        sa.Column('checked_at', sa.DateTime(timezone=True)), sa.Column('synced_at', sa.DateTime(timezone=True)),
        sa.Column('error', sa.String(500)), sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade():
    op.drop_table('sales_bi_workbooks')
    op.drop_table('sales_bi_config')
