"""Typed customer documents; preserve untyped operational history."""
from alembic import op
import sqlalchemy as sa

revision = 's1b2c3d4e5f6'
down_revision = 'r0a1b2c3d4e5'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('clientes', sa.Column('documentos', sa.JSON(), nullable=False, server_default='[]'))
    op.add_column('pdv_clientes', sa.Column('doc_tipo', sa.String(5)))
    op.add_column('pdv_clientes', sa.Column('doc_pais', sa.String(2)))
    # An old PDV doc may be CPF, RG, CI or RUC: do not infer its type by digits.
    # The old directory CPF remains available as Brazilian identity evidence.


def downgrade():
    raise RuntimeError('Preserve typed identity documents; use a forward migration.')
