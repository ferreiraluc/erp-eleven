"""merge heads

Revision ID: 3a834c0880f9
Revises: 847cdc1e7e5a, 9572ac0c4129
Create Date: 2025-08-05 19:43:13.210757

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3a834c0880f9'
down_revision: Union[str, None] = ('847cdc1e7e5a', '9572ac0c4129')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
