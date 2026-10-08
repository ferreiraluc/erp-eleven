"""Consolidate catalog labels without merging products or changing history."""
from alembic import op
import sqlalchemy as sa
from app.services.inventory_taxonomy_v1 import FIELDS, key, vocabulary

revision = 'd6e7f8a9b0c1'
down_revision = 'c5d6e7f8a9b0'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    op.create_table('inventory_taxonomy_snapshot_v1',
        sa.Column('item_id', sa.String(36), primary_key=True),
        sa.Column('brand', sa.String(100)), sa.Column('category', sa.String(100)),
        sa.Column('color', sa.String(50)))
    rows = connection.execute(sa.text('SELECT id, brand, category, color FROM inventory_items WHERE deleted_at IS NULL')).mappings().all()
    labels = {field: vocabulary([row[field] for row in rows], field) for field in FIELDS}
    for row in rows:
        values = {field: labels[field].get(key(row[field], field), row[field]) for field in FIELDS}
        if any(values[field] != row[field] for field in FIELDS):
            connection.execute(sa.text('INSERT INTO inventory_taxonomy_snapshot_v1 (item_id, brand, category, color) VALUES (:item_id, :brand, :category, :color)'),
                               dict(item_id=str(row['id']), **{field: row[field] for field in FIELDS}))
            connection.execute(sa.text('UPDATE inventory_items SET brand=:brand, category=:category, color=:color WHERE id=:id'), dict(id=row['id'], **values))


def downgrade():
    raise RuntimeError('Preserve o catálogo e o snapshot; restauração exige migração explícita para não sobrescrever edições posteriores.')
