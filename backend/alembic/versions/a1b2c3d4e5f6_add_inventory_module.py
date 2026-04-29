"""add inventory module

Revision ID: a1b2c3d4e5f6
Revises: 3a834c0880f9
Create Date: 2026-04-28 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '3a834c0880f9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # suppliers
    op.create_table(
        'suppliers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('contact', sa.String(200)),
        sa.Column('is_active', sa.Boolean(), default=True, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp()),
    )

    # inventory_items
    movement_type_enum = postgresql.ENUM('entry', 'exit', 'adjustment', 'transfer', name='movementtype')
    movement_type_enum.create(op.get_bind())

    session_status_enum = postgresql.ENUM('open', 'counting', 'reviewing', 'applied', 'cancelled', name='sessionstatus')
    session_status_enum.create(op.get_bind())

    op.create_table(
        'inventory_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('category', sa.String(100)),
        sa.Column('size', sa.String(50)),
        sa.Column('color', sa.String(50)),
        sa.Column('unit', sa.String(20), server_default='un'),
        sa.Column('location', sa.String(100)),
        sa.Column('barcode', sa.String(200)),
        sa.Column('sku_internal', sa.String(50), unique=True, nullable=False),
        sa.Column('supplier_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('suppliers.id'), nullable=True),
        sa.Column('cost_price', sa.DECIMAL(12, 2), server_default='0'),
        sa.Column('sale_price', sa.DECIMAL(12, 2), server_default='0'),
        sa.Column('currency', sa.String(10), server_default='PYG'),
        sa.Column('min_stock', sa.Integer(), server_default='0'),
        sa.Column('max_stock', sa.Integer(), server_default='0'),
        sa.Column('current_stock', sa.Integer(), server_default='0'),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('usuarios.id'), nullable=True),
    )

    op.create_index('idx_inventory_items_barcode', 'inventory_items', ['barcode'])
    op.create_index('idx_inventory_items_category', 'inventory_items', ['category'])

    # stock_movements
    op.create_table(
        'stock_movements',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('item_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('inventory_items.id'), nullable=False),
        sa.Column('movement_type', movement_type_enum, nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('quantity_before', sa.Integer(), nullable=False),
        sa.Column('quantity_after', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(500)),
        sa.Column('reference_type', sa.String(50)),
        sa.Column('reference_id', sa.String(100)),
        sa.Column('unit_cost', sa.DECIMAL(12, 2)),
        sa.Column('location_from', sa.String(100)),
        sa.Column('location_to', sa.String(100)),
        sa.Column('notes', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('usuarios.id'), nullable=True),
    )

    op.create_index('idx_stock_movements_item', 'stock_movements', ['item_id'])
    op.create_index('idx_stock_movements_created_at', 'stock_movements', ['created_at'])

    # inventory_sessions
    op.create_table(
        'inventory_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('status', session_status_enum, server_default='open'),
        sa.Column('location_filter', sa.String(100)),
        sa.Column('category_filter', sa.String(100)),
        sa.Column('started_at', sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.Column('finished_at', sa.DateTime()),
        sa.Column('applied_at', sa.DateTime()),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('usuarios.id'), nullable=True),
        sa.Column('approved_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('usuarios.id'), nullable=True),
        sa.Column('notes', sa.Text()),
    )

    # inventory_session_items
    op.create_table(
        'inventory_session_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('inventory_sessions.id'), nullable=False),
        sa.Column('item_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('inventory_items.id'), nullable=False),
        sa.Column('system_quantity', sa.Integer(), nullable=False),
        sa.Column('counted_quantity', sa.Integer()),
        sa.Column('scanned_at', sa.DateTime()),
        sa.Column('counted_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('usuarios.id'), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('inventory_session_items')
    op.drop_table('inventory_sessions')
    op.drop_index('idx_stock_movements_created_at', table_name='stock_movements')
    op.drop_index('idx_stock_movements_item', table_name='stock_movements')
    op.drop_table('stock_movements')
    op.drop_index('idx_inventory_items_category', table_name='inventory_items')
    op.drop_index('idx_inventory_items_barcode', table_name='inventory_items')
    op.drop_table('inventory_items')
    op.drop_table('suppliers')
    op.execute('DROP TYPE IF EXISTS movementtype')
    op.execute('DROP TYPE IF EXISTS sessionstatus')
