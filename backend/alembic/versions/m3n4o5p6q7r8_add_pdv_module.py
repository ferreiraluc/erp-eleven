"""add PDV module tables

Revision ID: m3n4o5p6q7r8
Revises: l2m3n4o5p6q7
Create Date: 2026-05-13 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = 'm3n4o5p6q7r8'
down_revision = 'l2m3n4o5p6q7'
branch_labels = None
depends_on = None


def upgrade():
    # pdv_clientes
    op.create_table(
        'pdv_clientes',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('nome', sa.String(200), nullable=False),
        sa.Column('doc', sa.String(30), nullable=True),
        sa.Column('telefone', sa.String(20), nullable=True),
        sa.Column('email', sa.String(100), nullable=True),
        sa.Column('tipo', sa.String(20), server_default='varejo'),
        sa.Column('limite_fiado_gs', sa.Numeric(15, 2), server_default='0'),
        sa.Column('saldo_fiado_gs', sa.Numeric(15, 2), server_default='0'),
        sa.Column('notas', sa.Text, nullable=True),
        sa.Column('ativo', sa.Boolean, server_default='true'),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('usuarios.id'), nullable=True),
    )
    op.create_index('idx_pdv_clientes_nome', 'pdv_clientes', ['nome'])
    op.create_index('idx_pdv_clientes_tipo', 'pdv_clientes', ['tipo'])

    # pdv_sales
    op.create_table(
        'pdv_sales',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('vendedor_id', UUID(as_uuid=True), sa.ForeignKey('usuarios.id'), nullable=True),
        sa.Column('cliente_id', UUID(as_uuid=True), sa.ForeignKey('pdv_clientes.id'), nullable=True),
        sa.Column('cliente_nome', sa.String(200), nullable=True),
        sa.Column('subtotal_gs', sa.Numeric(15, 2), server_default='0'),
        sa.Column('desconto_gs', sa.Numeric(15, 2), server_default='0'),
        sa.Column('total_gs', sa.Numeric(15, 2), server_default='0'),
        sa.Column('status', sa.String(20), server_default='completed'),
        sa.Column('stock_applied', sa.Boolean, server_default='false'),
        sa.Column('notas', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('usuarios.id'), nullable=True),
    )
    op.create_index('idx_pdv_sales_created_at', 'pdv_sales', ['created_at'])
    op.create_index('idx_pdv_sales_vendedor', 'pdv_sales', ['vendedor_id'])
    op.create_index('idx_pdv_sales_cliente', 'pdv_sales', ['cliente_id'])

    # pdv_sale_items
    op.create_table(
        'pdv_sale_items',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('sale_id', UUID(as_uuid=True), sa.ForeignKey('pdv_sales.id', ondelete='CASCADE'), nullable=False),
        sa.Column('item_id', UUID(as_uuid=True), sa.ForeignKey('inventory_items.id'), nullable=True),
        sa.Column('item_name', sa.String(300), nullable=False),
        sa.Column('item_sku', sa.String(50), nullable=True),
        sa.Column('item_category', sa.String(100), nullable=True),
        sa.Column('item_size', sa.String(20), nullable=True),
        sa.Column('item_color', sa.String(50), nullable=True),
        sa.Column('quantity', sa.Numeric(10, 3), server_default='1'),
        sa.Column('unit_price_gs', sa.Numeric(15, 2), nullable=False),
        sa.Column('original_price_gs', sa.Numeric(15, 2), nullable=True),
        sa.Column('discount_gs', sa.Numeric(15, 2), server_default='0'),
        sa.Column('total_gs', sa.Numeric(15, 2), nullable=False),
        sa.Column('is_avulso', sa.Boolean, server_default='false'),
        sa.Column('location', sa.String(20), server_default='loja'),
    )
    op.create_index('idx_pdv_sale_items_sale', 'pdv_sale_items', ['sale_id'])

    # pdv_payments
    op.create_table(
        'pdv_payments',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('sale_id', UUID(as_uuid=True), sa.ForeignKey('pdv_sales.id', ondelete='CASCADE'), nullable=False),
        sa.Column('cambista_id', UUID(as_uuid=True), sa.ForeignKey('cambistas.id'), nullable=True),
        sa.Column('method', sa.String(30), nullable=False),
        sa.Column('currency', sa.String(3), server_default='GS'),
        sa.Column('amount_original', sa.Numeric(15, 2), nullable=False),
        sa.Column('exchange_rate', sa.Numeric(15, 6), server_default='1'),
        sa.Column('amount_gs', sa.Numeric(15, 2), nullable=False),
        sa.Column('reference', sa.String(200), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
    )
    op.create_index('idx_pdv_payments_sale', 'pdv_payments', ['sale_id'])

    # pdv_fiado_movements
    op.create_table(
        'pdv_fiado_movements',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('cliente_id', UUID(as_uuid=True), sa.ForeignKey('pdv_clientes.id'), nullable=False),
        sa.Column('sale_id', UUID(as_uuid=True), sa.ForeignKey('pdv_sales.id'), nullable=True),
        sa.Column('tipo', sa.String(10), nullable=False),
        sa.Column('valor_gs', sa.Numeric(15, 2), nullable=False),
        sa.Column('saldo_gs', sa.Numeric(15, 2), nullable=False),
        sa.Column('notas', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('usuarios.id'), nullable=True),
    )
    op.create_index('idx_pdv_fiado_cliente', 'pdv_fiado_movements', ['cliente_id'])


def downgrade():
    op.drop_table('pdv_fiado_movements')
    op.drop_table('pdv_payments')
    op.drop_table('pdv_sale_items')
    op.drop_table('pdv_sales')
    op.drop_table('pdv_clientes')
