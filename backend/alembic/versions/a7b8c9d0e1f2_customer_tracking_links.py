"""Direct customer links for parcels, preserving explicit order relationships."""
from alembic import op
import sqlalchemy as sa

revision = "a7b8c9d0e1f2"
down_revision = "z6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("rastreamentos", sa.Column("cliente_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_rastreamentos_cliente_id", "rastreamentos", "clientes", ["cliente_id"], ["id"])
    op.create_index("ix_rastreamentos_cliente_id", "rastreamentos", ["cliente_id"])
    op.create_index("ix_rastreamentos_pedido_id", "rastreamentos", ["pedido_id"])
    op.create_index("ix_pedidos_cliente_id", "pedidos", ["cliente_id"])
    # Only an existing foreign key is evidence. Names are never a migration match.
    op.execute("""UPDATE rastreamentos AS r SET cliente_id = p.cliente_id
                  FROM pedidos AS p WHERE r.pedido_id = p.id AND p.cliente_id IS NOT NULL""")


def downgrade():
    raise RuntimeError("Os vínculos de clientes preservam histórico operacional. Reversão exige migração explícita.")
