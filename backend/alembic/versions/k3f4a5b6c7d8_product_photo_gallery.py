"""Four optional gallery photos, read only when opening an individual product."""
from alembic import op
import sqlalchemy as sa

revision = 'k3f4a5b6c7d8'
down_revision = 'j2e3f4a5b6c7'
branch_labels = None
depends_on = None


def upgrade():
    # Nullable, no rewrite/backfill of the existing catalog or original photos.
    op.add_column('inventory_items', sa.Column('additional_images', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('inventory_items', 'additional_images')
