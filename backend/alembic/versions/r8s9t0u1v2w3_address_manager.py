"""Address manager and immutable print snapshots."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
revision='r8s9t0u1v2w3'
down_revision='q7r8s9t0u1v2'
branch_labels=None
depends_on=None


def upgrade():
    op.add_column('assistant_deliveries',sa.Column('document_url',sa.String(2000)))
    op.create_table('saved_addresses',sa.Column('id',UUID(as_uuid=True),primary_key=True),sa.Column('label',sa.String(120),nullable=False),
        sa.Column('cliente_id',UUID(as_uuid=True),sa.ForeignKey('clientes.id')),sa.Column('pdv_cliente_id',UUID(as_uuid=True),sa.ForeignKey('pdv_clientes.id')),
        sa.Column('data',sa.JSON(),nullable=False),sa.Column('active',sa.Boolean(),nullable=False),sa.Column('version',sa.Integer(),nullable=False),
        sa.Column('created_by',UUID(as_uuid=True),sa.ForeignKey('usuarios.id'),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_saved_addresses_cliente_id','saved_addresses',['cliente_id'])
    op.create_index('ix_saved_addresses_pdv_cliente_id','saved_addresses',['pdv_cliente_id'])
    op.create_table('print_layouts',sa.Column('id',sa.String(30),primary_key=True),sa.Column('name',sa.String(100),nullable=False),
        sa.Column('config',sa.JSON(),nullable=False),sa.Column('version',sa.Integer(),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False))
    op.add_column('print_senders',sa.Column('data',sa.JSON()))
    op.add_column('print_senders',sa.Column('active',sa.Boolean(),nullable=False,server_default=sa.true()))
    op.add_column('print_senders',sa.Column('version',sa.Integer(),nullable=False,server_default='1'))
    op.add_column('print_jobs',sa.Column('snapshot',sa.JSON()))
    op.add_column('print_jobs',sa.Column('address_id',UUID(as_uuid=True),sa.ForeignKey('saved_addresses.id')))
    op.add_column('print_jobs',sa.Column('source',sa.String(20),nullable=False,server_default='upload'))
    op.add_column('print_jobs',sa.Column('parent_id',UUID(as_uuid=True),sa.ForeignKey('print_jobs.id')))
    op.execute("""UPDATE print_jobs j SET snapshot = a.payload::json, source = 'bot'
                  FROM assistant_actions a WHERE a.result_id = j.id AND a.kind = 'impressao'""")
    op.create_table('freight_orders',sa.Column('id',UUID(as_uuid=True),primary_key=True),sa.Column('request_key',UUID(as_uuid=True),unique=True,nullable=False),
        sa.Column('user_id',UUID(as_uuid=True),sa.ForeignKey('usuarios.id'),nullable=False),sa.Column('address_id',UUID(as_uuid=True),sa.ForeignKey('saved_addresses.id')),
        sa.Column('environment',sa.String(16),nullable=False),sa.Column('state',sa.String(30),nullable=False),sa.Column('payload',sa.JSON(),nullable=False),
        sa.Column('rates',sa.JSON(),nullable=False),sa.Column('provider_id',sa.String(100)),sa.Column('service',sa.Integer()),sa.Column('price',sa.Numeric(12,2)),
        sa.Column('tracking',sa.String(100)),sa.Column('label_url',sa.String(2000)),sa.Column('error',sa.String(200)),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False))


def downgrade():
    op.drop_column('assistant_deliveries','document_url')
    op.drop_table('freight_orders')
    for c in ['parent_id','source','address_id','snapshot']:op.drop_column('print_jobs',c)
    for c in ['version','active','data']:op.drop_column('print_senders',c)
    op.drop_table('print_layouts');op.drop_table('saved_addresses')
