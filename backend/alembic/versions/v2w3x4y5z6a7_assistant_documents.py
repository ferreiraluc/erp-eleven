"""Temporary Telegram file references; PDF contents are never stored in the ERP."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision='v2w3x4y5z6a7'
down_revision='u1v2w3x4y5z6'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('assistant_messages',sa.Column('attachment',JSONB()))

def downgrade():
    op.drop_column('assistant_messages','attachment')
