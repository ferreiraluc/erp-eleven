"""Explicit PDV link to the customer directory; preserves financial identities."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'c5d6e7f8a9b0'
down_revision = 'b4c5d6e7f8a9'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('pdv_clientes', sa.Column('cadastro_cliente_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_pdv_clientes_cadastro', 'pdv_clientes', 'clientes', ['cadastro_cliente_id'], ['id'])
    op.create_index('ix_pdv_clientes_cadastro_cliente_id', 'pdv_clientes', ['cadastro_cliente_id'])


def downgrade():
    raise RuntimeError('Preserve os vínculos dos clientes; use migração explícita.')
