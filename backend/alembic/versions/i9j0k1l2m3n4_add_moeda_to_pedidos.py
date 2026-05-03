"""add moeda to pedidos

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-05-03

"""
revision = 'i9j0k1l2m3n4'
down_revision = 'h8i9j0k1l2m3'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('pedidos', sa.Column('moeda', sa.String(3), nullable=False, server_default='R$'))


def downgrade():
    op.drop_column('pedidos', 'moeda')
