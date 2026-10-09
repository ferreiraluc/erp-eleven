"""Allow the USDT payment unit without changing historical payment rows."""
from alembic import op
import sqlalchemy as sa

revision = 'f8a9b0c1d2e3'
down_revision = 'e7f8a9b0c1d2'
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name == 'postgresql':
        op.alter_column('pdv_payments', 'currency', existing_type=sa.String(3), type_=sa.String(4))


def downgrade():
    raise RuntimeError('Preserve o histórico de pagamentos USDT; reversão exige revisão explícita.')
