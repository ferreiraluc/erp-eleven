"""Private sender profiles for address printing."""
from alembic import op
import sqlalchemy as sa
revision = 'q7r8s9t0u1v2'
down_revision = 'p6q7r8s9t0u1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('print_senders', sa.Column('id', sa.String(30), primary_key=True),
                    sa.Column('name', sa.String(100), nullable=False),
                    sa.Column('lines', sa.JSON(), nullable=False))


def downgrade():
    op.drop_table('print_senders')
