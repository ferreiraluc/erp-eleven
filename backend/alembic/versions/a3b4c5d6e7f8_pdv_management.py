"""Reviewed sale corrections, returns and preserved revisions."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
revision='a3b4c5d6e7f8'
down_revision='f2a3b4c5d6e7'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('pdv_sales',sa.Column('version',sa.Integer(),nullable=False,server_default='1'))
    op.add_column('pdv_sales',sa.Column('refunded_gs',sa.Numeric(15,2),nullable=False,server_default='0'))
    op.add_column('pdv_sales',sa.Column('fiado_reversed_gs',sa.Numeric(15,2),nullable=False,server_default='0'))
    op.add_column('pdv_sales',sa.Column('deleted_at',sa.DateTime(timezone=True),nullable=True))
    op.add_column('pdv_sale_items',sa.Column('returned_quantity',sa.Numeric(10,3),nullable=False,server_default='0'))
    op.create_table('pdv_sale_events',
        sa.Column('id',UUID(as_uuid=True),primary_key=True),
        sa.Column('sale_id',UUID(as_uuid=True),sa.ForeignKey('pdv_sales.id'),nullable=False),
        sa.Column('request_id',UUID(as_uuid=True),nullable=False,unique=True),
        sa.Column('fingerprint',sa.String(64),nullable=False),
        sa.Column('operation',sa.String(20),nullable=False),
        sa.Column('reason',sa.Text(),nullable=False),
        sa.Column('before',sa.JSON(),nullable=False),sa.Column('after',sa.JSON(),nullable=False),
        sa.Column('effects',sa.JSON(),nullable=False),
        sa.Column('created_by',UUID(as_uuid=True),sa.ForeignKey('usuarios.id'),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_pdv_sale_events_sale','pdv_sale_events',['sale_id','created_at'])
    op.create_index('ix_pdv_sales_deleted_at','pdv_sales',['deleted_at'])

def downgrade():
    raise RuntimeError('Preserve o histórico de revisões e devoluções; downgrade requer migração explícita.')
