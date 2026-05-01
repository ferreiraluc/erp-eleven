"""add custo_emissao to rastreamentos

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'rastreamentos',
        sa.Column('custo_emissao', sa.DECIMAL(10, 2), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('rastreamentos', 'custo_emissao')
