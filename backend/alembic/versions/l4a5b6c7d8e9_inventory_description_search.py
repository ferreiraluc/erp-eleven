"""Index description keywords without rewriting products or blocking catalog writes."""
from alembic import op
import sqlalchemy as sa

revision = 'l4a5b6c7d8e9'
down_revision = 'k3f4a5b6c7d8'
branch_labels = None
depends_on = None

ACCENTS = 'áàâãäéèêëíìîïóòôõöúùûüçñ'
ASCII = 'aaaaaeeeeiiiiooooouuuucn'
INDEX = 'ix_inventory_description_trgm'


def upgrade():
    if op.get_bind().dialect.name != 'postgresql':
        return
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public')
    # Must match inventory_search.normalizer, including COALESCE and accents.
    # A separate partial index lets bitmap OR combine with existing search/facets.
    with op.get_context().autocommit_block():
        invalid = op.get_bind().execute(sa.text('''SELECT 1 FROM pg_index i
            JOIN pg_class c ON c.oid=i.indexrelid JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname=current_schema() AND c.relname=:name AND NOT i.indisvalid'''),
            {'name': INDEX}).scalar()
        if invalid:
            op.execute(f'DROP INDEX CONCURRENTLY "{INDEX}"')
        op.execute(f'''CREATE INDEX CONCURRENTLY IF NOT EXISTS {INDEX}
            ON inventory_items USING gin
            (lower(translate(coalesce(description, ''), '{ACCENTS + ACCENTS.upper()}', '{ASCII * 2}')) public.gin_trgm_ops)
            WHERE deleted_at IS NULL''')
    op.execute('ANALYZE inventory_items')


def downgrade():
    if op.get_bind().dialect.name == 'postgresql':
        with op.get_context().autocommit_block():
            op.execute(f'DROP INDEX CONCURRENTLY IF EXISTS {INDEX}')
