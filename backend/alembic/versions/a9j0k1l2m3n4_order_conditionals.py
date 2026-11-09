"""Conditional orders keep delivered pieces and partial refunds auditable."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'a9j0k1l2m3n4'
down_revision = 'z8i9j0k1l2m3'
branch_labels = None
depends_on = None


def upgrade():
    uid = postgresql.UUID(as_uuid=True)
    op.drop_constraint('ck_pedidos_commerce_status', 'pedidos', type_='check')
    op.create_check_constraint('ck_pedidos_commerce_status', 'pedidos', "commerce_status IS NULL OR commerce_status IN ('reserved','conditional','returned','completed','cancelled')")
    for column in (sa.Column('delivered_at', sa.DateTime(timezone=True)),
                   sa.Column('delivered_subtotal_gs', sa.Numeric(15, 2)),
                   sa.Column('delivered_total_gs', sa.Numeric(15, 2))):
        op.add_column('pedidos', column)
    op.add_column('pedido_items', sa.Column('returned_quantity', sa.Integer(), nullable=False, server_default='0'))
    op.create_check_constraint('ck_pedido_item_returned', 'pedido_items', 'returned_quantity >= 0 AND returned_quantity <= quantity')
    op.create_table('pedido_payment_refunds',
        sa.Column('id', uid, primary_key=True),
        sa.Column('payment_id', uid, sa.ForeignKey('pedido_payments.id'), nullable=False),
        sa.Column('amount_gs', sa.Numeric(15, 2), nullable=False),
        sa.Column('amount_original', sa.Numeric(15, 2), nullable=False),
        sa.Column('card_fee_gs', sa.Numeric(15, 2), nullable=False, server_default='0'),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', uid, sa.ForeignKey('usuarios.id'), nullable=False),
        sa.CheckConstraint('amount_gs > 0 AND amount_original >= 0 AND card_fee_gs >= 0', name='ck_pedido_refund_positive'))
    op.create_index('ix_pedido_payment_refunds_payment_id', 'pedido_payment_refunds', ['payment_id'])


def downgrade():
    # An automatic downgrade cannot safely erase physical deliveries or refunds.
    bind = op.get_bind()
    if bind.execute(sa.text('SELECT 1 FROM pedidos WHERE delivered_at IS NOT NULL LIMIT 1')).first() or bind.execute(sa.text('SELECT 1 FROM pedido_payment_refunds LIMIT 1')).first():
        raise RuntimeError('Conditional deliveries/refunds exist; preserve their operational history.')
    op.drop_table('pedido_payment_refunds')
    op.drop_constraint('ck_pedido_item_returned', 'pedido_items', type_='check')
    op.drop_column('pedido_items', 'returned_quantity')
    for name in ('delivered_total_gs', 'delivered_subtotal_gs', 'delivered_at'):
        op.drop_column('pedidos', name)
    op.drop_constraint('ck_pedidos_commerce_status', 'pedidos', type_='check')
    op.create_check_constraint('ck_pedidos_commerce_status', 'pedidos', "commerce_status IS NULL OR commerce_status IN ('reserved','completed','cancelled')")
