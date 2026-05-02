"""add clientes module

Revision ID: g7h8i9j0k1l2
Revises: f6a7b8c9d0e1
Create Date: 2026-05-02

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = 'g7h8i9j0k1l2'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'clientes',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('nome', sa.String(200), nullable=False),
        sa.Column('telefone', sa.String(20)),
        sa.Column('email', sa.String(100)),
        sa.Column('cpf', sa.String(14), unique=True, nullable=True),
        sa.Column('endereco', sa.Text()),
        sa.Column('ativo', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.current_timestamp()),
    )
    op.create_index('idx_clientes_nome', 'clientes', ['nome'])
    op.create_index('idx_clientes_telefone', 'clientes', ['telefone'])
    op.create_index('idx_clientes_email', 'clientes', ['email'])

    # FK cliente_id em pedidos
    op.add_column('pedidos', sa.Column('cliente_id', UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'fk_pedidos_cliente_id',
        'pedidos', 'clientes',
        ['cliente_id'], ['id'],
        ondelete='SET NULL',
    )
    op.create_index('idx_pedidos_cliente_id', 'pedidos', ['cliente_id'])


def downgrade():
    op.drop_index('idx_pedidos_cliente_id', table_name='pedidos')
    op.drop_constraint('fk_pedidos_cliente_id', 'pedidos', type_='foreignkey')
    op.drop_column('pedidos', 'cliente_id')
    op.drop_index('idx_clientes_email', table_name='clientes')
    op.drop_index('idx_clientes_telefone', table_name='clientes')
    op.drop_index('idx_clientes_nome', table_name='clientes')
    op.drop_table('clientes')
