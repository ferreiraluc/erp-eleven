"""Commercial orders reserve stock and retain deposits until one PDV sale."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'z8i9j0k1l2m3'
down_revision = 'y7h8i9j0k1l2'
branch_labels = None
depends_on = None


def upgrade():
    uid = postgresql.UUID(as_uuid=True)
    for location in ('loja', 'deposito'):
        name = f'reserved_{location}'
        op.add_column('inventory_items', sa.Column(name, sa.Integer(), nullable=False, server_default='0'))
        op.create_check_constraint(f'ck_inventory_{name}', 'inventory_items', f'{name} >= 0')
    for column in (
        sa.Column('commerce_status', sa.String(20)),
        sa.Column('commerce_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('pdv_cliente_id', uid), sa.Column('vendedor_id', uid), sa.Column('sale_id', uid),
        sa.Column('usd_rate_gs', sa.Numeric(12, 4)),
        sa.Column('subtotal_gs', sa.Numeric(15, 2)), sa.Column('desconto_gs', sa.Numeric(15, 2)),
        sa.Column('total_gs', sa.Numeric(15, 2)), sa.Column('paid_gs', sa.Numeric(15, 2)),
        sa.Column('reserved_at', sa.DateTime(timezone=True)), sa.Column('commerce_notes', sa.Text()),
    ):
        op.add_column('pedidos', column)
    op.create_foreign_key('fk_pedido_pdv_cliente', 'pedidos', 'pdv_clientes', ['pdv_cliente_id'], ['id'])
    op.create_foreign_key('fk_pedido_vendedor', 'pedidos', 'usuarios', ['vendedor_id'], ['id'])
    op.create_foreign_key('fk_pedido_sale', 'pedidos', 'pdv_sales', ['sale_id'], ['id'])
    op.create_unique_constraint('uq_pedidos_sale_id', 'pedidos', ['sale_id'])
    op.create_index('ix_pedidos_commerce_status', 'pedidos', ['commerce_status'])
    op.create_check_constraint('ck_pedidos_commerce_status', 'pedidos', "commerce_status IS NULL OR commerce_status IN ('reserved','completed','cancelled')")
    op.create_table('pedido_items',
        sa.Column('id', uid, primary_key=True),
        sa.Column('pedido_id', uid, sa.ForeignKey('pedidos.id'), nullable=False),
        sa.Column('item_id', uid, sa.ForeignKey('inventory_items.id'), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('item_name', sa.String(300), nullable=False), sa.Column('item_sku', sa.String(50)),
        sa.Column('item_size', sa.String(50)), sa.Column('item_color', sa.String(50)), sa.Column('item_category', sa.String(100)),
        sa.Column('location', sa.String(20), nullable=False), sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('unit_price_gs', sa.Numeric(15, 2), nullable=False), sa.Column('total_gs', sa.Numeric(15, 2), nullable=False),
        sa.CheckConstraint('quantity > 0', name='ck_pedido_item_quantity'),
        sa.CheckConstraint("location IN ('loja','deposito')", name='ck_pedido_item_location'),
        sa.CheckConstraint('unit_price_gs >= 0 AND total_gs >= 0', name='ck_pedido_item_prices'),
    )
    op.create_index('ix_pedido_items_pedido_id', 'pedido_items', ['pedido_id'])
    op.create_index('ix_pedido_items_item_id', 'pedido_items', ['item_id'])
    op.create_table('pedido_payments',
        sa.Column('id', uid, primary_key=True), sa.Column('pedido_id', uid, sa.ForeignKey('pedidos.id'), nullable=False),
        sa.Column('method', sa.String(30), nullable=False), sa.Column('currency', sa.String(4), nullable=False),
        sa.Column('amount_original', sa.Numeric(15, 2), nullable=False), sa.Column('exchange_rate', sa.Numeric(15, 6), nullable=False),
        sa.Column('amount_gs', sa.Numeric(15, 2), nullable=False),
        sa.Column('card_fee_gs', sa.Numeric(15, 2), nullable=False, server_default='0'),
        sa.Column('card_fee_percent', sa.Numeric(5, 2), nullable=False, server_default='0'),
        sa.Column('cambista_id', uid, sa.ForeignKey('cambistas.id')), sa.Column('reference', sa.String(200)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', uid, sa.ForeignKey('usuarios.id'), nullable=False),
        sa.Column('reversed_at', sa.DateTime(timezone=True)), sa.Column('reversed_by', uid, sa.ForeignKey('usuarios.id')),
        sa.Column('reversal_reason', sa.Text()),
        sa.Column('sale_payment_id', uid, sa.ForeignKey('pdv_payments.id', ondelete='SET NULL'), unique=True),
        sa.CheckConstraint('amount_gs > 0', name='ck_pedido_payment_positive'),
    )
    op.create_index('ix_pedido_payments_pedido_id', 'pedido_payments', ['pedido_id'])
    op.create_table('pedido_operations',
        sa.Column('id', uid, primary_key=True), sa.Column('pedido_id', uid, sa.ForeignKey('pedidos.id'), nullable=False),
        sa.Column('actor_id', uid, sa.ForeignKey('usuarios.id'), nullable=False),
        sa.Column('operation', sa.String(80), nullable=False), sa.Column('fingerprint', sa.String(64), nullable=False),
        sa.Column('before', sa.JSON()), sa.Column('after', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_pedido_operations_pedido_id', 'pedido_operations', ['pedido_id'])


def downgrade():
    raise RuntimeError('Preserve reservations, deposits and order history; use a forward migration.')
