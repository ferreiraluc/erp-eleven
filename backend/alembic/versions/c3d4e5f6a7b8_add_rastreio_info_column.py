"""add rastreio_info column to rastreamentos

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6
Create Date: 2026-05-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'c3d4e5f6a7b8'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'rastreamentos',
        sa.Column('rastreio_info', postgresql.JSONB(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('rastreamentos', 'rastreio_info')
