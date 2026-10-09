"""Persist bounded previews and index the existing catalog search expressions."""
from alembic import op
import sqlalchemy as sa

revision = 'e7f8a9b0c1d2'
down_revision = 'd6e7f8a9b0c1'
branch_labels = None
depends_on = None

ACCENTS = 'áàâãäéèêëíìîïóòôõöúùûüçñ'
ASCII = 'aaaaaeeeeiiiiooooouuuucn'


def upgrade():
    columns = {column['name'] for column in sa.inspect(op.get_bind()).get_columns('inventory_items')}
    if 'thumbnail_data' not in columns:
        op.add_column('inventory_items', sa.Column('thumbnail_data', sa.Text(), nullable=True))
    if 'thumbnail_ready' not in columns:
        op.add_column('inventory_items', sa.Column('thumbnail_ready', sa.Boolean(), nullable=False, server_default=sa.false()))
    if op.get_bind().dialect.name != 'postgresql':
        return
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public')
    op.execute('''CREATE OR REPLACE FUNCTION invalidate_inventory_thumbnail() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.image_data IS DISTINCT FROM OLD.image_data THEN
                NEW.thumbnail_data := NULL;
                NEW.thumbnail_ready := false;
            END IF;
            RETURN NEW;
        END $$''')
    op.execute('DROP TRIGGER IF EXISTS inventory_thumbnail_photo_change ON inventory_items')
    op.execute('''CREATE TRIGGER inventory_thumbnail_photo_change BEFORE UPDATE OF image_data
        ON inventory_items FOR EACH ROW EXECUTE FUNCTION invalidate_inventory_thumbnail()''')
    # Constants match inventory_search.normalizer exactly. Include every OR branch
    # (facets + literal identifiers), so PostgreSQL can combine bitmap indexes.
    expressions = [f"lower(translate(coalesce({column}, ''), '{ACCENTS + ACCENTS.upper()}', '{ASCII * 2}')) public.gin_trgm_ops"
                   for column in ('name', 'category', 'group_key', 'sku_internal', 'barcode', 'brand')]
    expressions += ['lower(sku_internal) public.gin_trgm_ops', 'lower(barcode) public.gin_trgm_ops']
    # Concurrent builds avoid blocking operational writes. Separate autocommit
    # statements are safe to retry with IF NOT EXISTS after a completed build.
    with op.get_context().autocommit_block():
        # A cancelled concurrent build leaves an invalid index. Repair only ours.
        names = ['ix_inventory_search_trgm', 'ix_inventory_catalog_order'] + [
            'ix_inventory_live_' + column for column in ('brand', 'category', 'color', 'size')]
        invalid = op.get_bind().execute(sa.text("""SELECT c.relname FROM pg_index i
            JOIN pg_class c ON c.oid=i.indexrelid JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname=current_schema() AND NOT i.indisvalid""")).scalars().all()
        for name in invalid:
            if name in names:
                op.execute(f'DROP INDEX CONCURRENTLY "{name}"')
        op.execute('CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_inventory_search_trgm ON inventory_items USING gin ('
                   + ', '.join(expressions) + ') WHERE deleted_at IS NULL')
        for column in ('brand', 'category', 'color', 'size'):
            op.execute(f'CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_inventory_live_{column} ON inventory_items ({column}) WHERE deleted_at IS NULL')
        op.execute('CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_inventory_catalog_order ON inventory_items (name, color, size, id) WHERE deleted_at IS NULL')
    op.execute('ANALYZE inventory_items')


def downgrade():
    raise RuntimeError('Preserve o catálogo; reversão exige revisão explícita.')
