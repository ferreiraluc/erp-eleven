"""add only taxa_desconto_pagamento column

Revision ID: 9572ac0c4129
Revises: 847cdc1e7e5a
Create Date: 2025-08-05 19:42:03.561096

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9572ac0c4129'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if column already exists
    conn = op.get_bind()
    result = conn.execute(sa.text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'vendas' 
        AND column_name = 'taxa_desconto_pagamento'
    """))
    
    if not result.fetchone():
        # Add the missing column
        op.add_column('vendas', sa.Column('taxa_desconto_pagamento', sa.DECIMAL(5,4), nullable=True, server_default='0'))


def downgrade() -> None:
    op.drop_column('vendas', 'taxa_desconto_pagamento')
