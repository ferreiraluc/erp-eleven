"""Preserve referenced products as historical records outside the catalog."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = 'f2a3b4c5d6e7'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('inventory_items', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('inventory_items', sa.Column('deleted_by', UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_inventory_deleted_by', 'inventory_items', 'usuarios', ['deleted_by'], ['id'])
    op.create_index('ix_inventory_items_deleted_at', 'inventory_items', ['deleted_at'])


def downgrade():
    raise RuntimeError('Remover a marca de exclusão reativa registros históricos. Planeje uma migração explícita preservando estes dados.')
