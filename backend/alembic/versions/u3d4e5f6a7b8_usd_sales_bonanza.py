"""Freeze the sales presentation rate and add opt-in Bonanza scheduling."""
from alembic import op
import sqlalchemy as sa

revision='u3d4e5f6a7b8'
down_revision='t2c3d4e5f6a7'
branch_labels=None
depends_on=None


def upgrade():
    op.add_column('pdv_sales',sa.Column('usd_rate_gs',sa.Numeric(12,4)))
    # Historical evidence only: never apply today's rate to an old sale.
    op.execute("""UPDATE pdv_sales s SET usd_rate_gs=COALESCE(
        (SELECT r.rate FROM exchange_rates r WHERE r.currency_pair='USD_TO_PYG'
         AND r.rate>0 AND r.created_at<=s.created_at ORDER BY r.created_at DESC,r.id DESC LIMIT 1),
        (SELECT MIN(p.exchange_rate) FROM pdv_payments p WHERE p.sale_id=s.id
         AND p.currency IN ('USD','USDT') AND p.exchange_rate>0
         HAVING MIN(p.exchange_rate)=MAX(p.exchange_rate)))""")
    op.create_table('exchange_sync',sa.Column('id',sa.String(16),primary_key=True),
        sa.Column('enabled',sa.Boolean(),nullable=False),
        sa.Column('last_attempt',sa.DateTime(timezone=True)),
        sa.Column('last_success',sa.DateTime(timezone=True)),
        sa.Column('source_at',sa.DateTime(timezone=True)),
        sa.Column('last_error',sa.String(40)))


def downgrade():
    raise RuntimeError('Preserve frozen sales rates; use a forward migration.')
