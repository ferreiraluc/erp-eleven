"""Catalog receiving lots, separate from stock balances and product families."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = 'j2e3f4a5b6c7'
down_revision = 'i1d2e3f4a5b6'
branch_labels = None
depends_on = None


def upgrade():
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table('inventory_receiving_lots',
        sa.Column('id', uuid, primary_key=True),
        sa.Column('name', sa.String(160), nullable=False),
        sa.Column('notes', sa.Text(), nullable=False),
        sa.Column('received_on', sa.Date(), nullable=False),
        sa.Column('created_by', uuid, sa.ForeignKey('usuarios.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('request_fingerprint', sa.String(64), nullable=False))
    op.create_table('inventory_receiving_lot_items',
        sa.Column('id', uuid, primary_key=True),
        sa.Column('lot_id', uuid, sa.ForeignKey('inventory_receiving_lots.id'), nullable=False),
        sa.Column('item_id', uuid, sa.ForeignKey('inventory_items.id', ondelete='SET NULL')),
        sa.Column('item_name', sa.String(200), nullable=False),
        sa.Column('item_sku', sa.String(50), nullable=False),
        sa.Column('created_by', uuid, sa.ForeignKey('usuarios.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('lot_id', 'item_id', name='uq_receiving_lot_item'))
    op.create_index('ix_inventory_receiving_lot_items_lot_id', 'inventory_receiving_lot_items', ['lot_id'])
    op.create_index('ix_inventory_receiving_lot_items_item_id', 'inventory_receiving_lot_items', ['item_id'])
    op.create_index('ix_inventory_live_created', 'inventory_items', ['created_at', 'id'], postgresql_where=sa.text('deleted_at IS NULL'))
    op.create_index('ix_inventory_receiving_lots_received_on', 'inventory_receiving_lots', ['received_on', 'created_at'])


def downgrade():
    op.drop_index('ix_inventory_live_created', table_name='inventory_items')
    op.drop_table('inventory_receiving_lot_items')
    op.drop_table('inventory_receiving_lots')
