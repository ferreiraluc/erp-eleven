"""Normalize known brands/clothing sizes; preserve every product and its history."""
from alembic import op
import sqlalchemy as sa
import logging
from app.services.inventory_taxonomy_v2 import canonical, canonical_size, normalized_size_name

revision = 'i1d2e3f4a5b6'
down_revision = 'h0c1d2e3f4a5'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    snapshot = op.create_table('inventory_catalog_snapshot_v2',
        sa.Column('item_id', sa.String(36), primary_key=True),
        sa.Column('before', sa.JSON(), nullable=False),
        sa.Column('after', sa.JSON(), nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    # Bounded batches, metadata only. No photos, balances or operational histories.
    last = None
    changed = 0
    while True:
        condition = ' AND id > :last' if last is not None else ''
        rows = connection.execute(sa.text('SELECT id, name, size, brand FROM inventory_items '
            'WHERE deleted_at IS NULL' + condition + ' ORDER BY id LIMIT 500'), {'last': last}).mappings().all()
        if not rows:
            break
        for row in rows:
            before = {key: row[key] for key in ('name', 'size', 'brand')}
            after = dict(before, size=canonical_size(row['size']), brand=canonical(row['brand'], 'brand'))
            after['name'] = normalized_size_name(row['name'], row['size'], after['size'])
            if before != after:
                changed += 1
                connection.execute(snapshot.insert(), dict(item_id=str(row['id']), before=before, after=after))
                connection.execute(sa.text('UPDATE inventory_items SET name=:name, size=:size, brand=:brand WHERE id=:id'),
                                   dict(id=row['id'], **after))
        last = rows[-1]['id']
    logging.getLogger('alembic.runtime.migration').info('Catalog aliases v2: %d products normalized with before/after snapshot; identities and balances preserved', changed)
    # Two existing S/P items may now share a size. Keep both identities and all
    # balances; create_variants detects equivalence and will not create a third.


def downgrade():
    raise RuntimeError('Preserve o snapshot e o histórico. Reversão exige revisão explícita para não sobrescrever edições posteriores.')
