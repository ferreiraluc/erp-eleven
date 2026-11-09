"""Archive order directories without deleting operational history.

Revision ID: b0k1l2m3n4o5
Revises: a9j0k1l2m3n4
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'b0k1l2m3n4o5'
down_revision = 'a9j0k1l2m3n4'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('pedidos', sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('pedidos', sa.Column('archived_by', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_pedidos_archived_by', 'pedidos', 'usuarios', ['archived_by'], ['id'])
    op.create_index('ix_pedidos_archived_at', 'pedidos', ['archived_at'])
    op.create_table('pedido_archive_operations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('actor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('usuarios.id'), nullable=False),
        sa.Column('fingerprint', sa.String(64), nullable=False),
        sa.Column('order_ids', sa.JSON(), nullable=False),
        sa.Column('result', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))


def downgrade():
    raise RuntimeError('O arquivo de pedidos preserva histórico operacional; use uma migração corretiva para avançar.')
