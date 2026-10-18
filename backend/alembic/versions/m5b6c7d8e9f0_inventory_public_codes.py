"""Allocate short catalog references while retaining every legacy SKU and UUID."""
from alembic import op
import sqlalchemy as sa

revision = 'm5b6c7d8e9f0'
down_revision = 'l4a5b6c7d8e9'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {column['name'] for column in sa.inspect(bind).get_columns('inventory_items')}
    if 'inventory_code' not in columns:
        op.add_column('inventory_items', sa.Column('inventory_code', sa.String(10), nullable=True))
    if bind.dialect.name != 'postgresql':
        return
    # The sequence is independent of product deletion, so public codes are not reused.
    op.execute('CREATE SEQUENCE IF NOT EXISTS inventory_code_seq MINVALUE 1 MAXVALUE 1073741824 NO CYCLE')
    op.execute('''CREATE OR REPLACE FUNCTION next_inventory_code() RETURNS text LANGUAGE plpgsql AS $$
        DECLARE
            alphabet constant text := '23456789ABCDEFGHJKLMNPQRSTUVWXYZ';
            value bigint := (nextval('inventory_code_seq') * 15485863 + 32452843) % 1073741824;
            result text := '';
        BEGIN
            FOR position IN 1..6 LOOP
                result := substr(alphabet, (value % 32)::integer + 1, 1) || result;
                value := value / 32;
            END LOOP;
            RETURN 'INV-' || result;
        END $$''')
    op.alter_column('inventory_items', 'inventory_code', server_default=sa.text('next_inventory_code()'))
    # Bounded transactions; do not select original images or change updated_at.
    with op.get_context().autocommit_block():
        while bind.execute(sa.text('''UPDATE inventory_items SET inventory_code=next_inventory_code()
            WHERE id IN (SELECT id FROM inventory_items WHERE inventory_code IS NULL ORDER BY id LIMIT 500)''')).rowcount:
            pass
        for name in ('ix_inventory_public_code',):
            invalid = bind.execute(sa.text('''SELECT 1 FROM pg_index i
                JOIN pg_class c ON c.oid=i.indexrelid JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname=current_schema() AND c.relname=:name AND NOT i.indisvalid'''), {'name': name}).scalar()
            if invalid:
                op.execute(f'DROP INDEX CONCURRENTLY "{name}"')
        op.execute('CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS ix_inventory_public_code ON inventory_items (inventory_code)')
        # The backfill creates pending GIN entries in existing search indexes.
        # Drain them before serving traffic; VACUUM does not block normal writes.
        op.execute('VACUUM (ANALYZE) inventory_items')


def downgrade():
    raise RuntimeError('Códigos públicos já emitidos devem permanecer reservados; reversão exige revisão explícita.')
