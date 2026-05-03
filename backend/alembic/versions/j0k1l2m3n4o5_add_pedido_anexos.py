"""add pedido_anexos

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
Create Date: 2026-05-03

"""
revision = 'j0k1l2m3n4o5'
down_revision = 'i9j0k1l2m3n4'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


def upgrade():
    op.create_table(
        'pedido_anexos',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('pedido_id', UUID(as_uuid=True), sa.ForeignKey('pedidos.id', ondelete='CASCADE'), nullable=False),
        sa.Column('nome_arquivo', sa.String(255), nullable=False),
        sa.Column('tipo_arquivo', sa.String(100), nullable=False),
        sa.Column('tamanho', sa.Integer, nullable=False),
        sa.Column('dados', sa.Text, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('usuarios.id'), nullable=True),
    )
    op.create_index('idx_pedido_anexos_pedido_id', 'pedido_anexos', ['pedido_id'])
    op.add_column('pedidos', sa.Column('anexos_count', sa.Integer, nullable=False, server_default='0'))


def downgrade():
    op.drop_column('pedidos', 'anexos_count')
    op.drop_index('idx_pedido_anexos_pedido_id')
    op.drop_table('pedido_anexos')
