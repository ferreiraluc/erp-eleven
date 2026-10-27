"""Concurrent quality-window indexes, separate from transactional table creation."""
from alembic import op
import sqlalchemy as sa

revision = 'q9f0a1b2c3d4'
down_revision = 'p8e9f0a1b2c3'
branch_labels = None
depends_on = None

INDEXES = {
    'ix_quality_inventory_recent': 'inventory_items (updated_at, id) WHERE deleted_at IS NULL AND is_active IS true',
    'ix_quality_customers_recent': 'clientes (updated_at, id) WHERE merged_into_id IS NULL',
    'ix_quality_addresses_recent': 'saved_addresses (updated_at, id) WHERE merged_into_id IS NULL',
    'ix_quality_print_jobs_state_time': 'print_jobs (status, created_at, id)',
}


def upgrade():
    if op.get_bind().dialect.name != 'postgresql':
        return
    # A cancelled concurrent build can leave an invalid named index. Repair only
    # this migration's known names so retrying a deploy cannot silently skip it.
    with op.get_context().autocommit_block():
        for name, definition in INDEXES.items():
            invalid = op.get_bind().execute(sa.text('''SELECT NOT i.indisvalid FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace JOIN pg_index i ON i.indexrelid = c.oid
                WHERE c.relname = :name AND n.nspname = current_schema()'''), {'name': name}).scalar()
            if invalid:
                op.execute(f'DROP INDEX CONCURRENTLY IF EXISTS {name}')
            op.execute(f'CREATE INDEX CONCURRENTLY IF NOT EXISTS {name} ON {definition}')


def downgrade():
    raise RuntimeError('Preserve diagnostic indexes and history; use a forward migration.')
