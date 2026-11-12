"""Add a restricted catalog profile without changing existing account access."""
from alembic import op
import sqlalchemy as sa

revision = 'c1l2m3n4o5p6'
down_revision = 'b0k1l2m3n4o5'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('usuarios', sa.Column('access_profile', sa.String(20), nullable=False, server_default='standard'))


def downgrade():
    raise RuntimeError('Remover o perfil ampliaria acessos restritos. Use uma migração corretiva para avançar.')
