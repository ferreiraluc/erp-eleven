"""Preserve explicitly consolidated customers as historical aliases."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'e1f2a3b4c5d6'
down_revision = 'd0e1f2a3b4c5'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('clientes', sa.Column('merged_into_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_clientes_merged_into', 'clientes', 'clientes', ['merged_into_id'], ['id'])
    op.create_index('ix_clientes_merged_into_id', 'clientes', ['merged_into_id'])
    op.create_check_constraint('ck_clientes_merge_not_self', 'clientes', 'merged_into_id IS NULL OR merged_into_id <> id')
    op.create_check_constraint('ck_clientes_merged_inactive', 'clientes', 'merged_into_id IS NULL OR ativo = false')


def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM clientes WHERE merged_into_id IS NOT NULL')).scalar():
        raise RuntimeError('Clientes consolidados existem; preserve suas referências antes de reverter.')
    op.drop_constraint('ck_clientes_merged_inactive', 'clientes', type_='check')
    op.drop_constraint('ck_clientes_merge_not_self', 'clientes', type_='check')
    op.drop_index('ix_clientes_merged_into_id', table_name='clientes')
    op.drop_constraint('fk_clientes_merged_into', 'clientes', type_='foreignkey')
    op.drop_column('clientes', 'merged_into_id')
