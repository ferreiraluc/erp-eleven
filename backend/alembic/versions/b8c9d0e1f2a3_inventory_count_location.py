"""Explicit location for new inventory counts; legacy sessions remain unscoped.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
"""
from alembic import op
import sqlalchemy as sa

revision = 'b8c9d0e1f2a3'
down_revision = 'a7b8c9d0e1f2'
branch_labels = None
depends_on = None


def upgrade():
    # Do not infer a count location from the old free-text location_filter.
    op.add_column('inventory_sessions', sa.Column('count_location', sa.String(20), nullable=True))


def downgrade():
    raise RuntimeError('Downgrade automático indisponível: remover count_location perde o escopo das contagens já registradas. Preserve os dados e planeje uma migração explícita.')
