"""Separate PDV ticket destination from existing A4 printers."""
from alembic import op
import sqlalchemy as sa

revision = 'h0c1d2e3f4a5'
down_revision = 'g9b0c1d2e3f4'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('print_devices', sa.Column('purpose', sa.String(20), nullable=False, server_default='documents'))
    op.add_column('print_devices', sa.Column('paper_width_mm', sa.Integer(), nullable=False, server_default='60'))
    op.add_column('print_devices', sa.Column('paper_height_mm', sa.Integer(), nullable=False, server_default='80'))
    op.add_column('print_devices', sa.Column('auto_receipts', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index('uq_print_device_auto_receipts', 'print_devices', ['auto_receipts'], unique=True,
                    postgresql_where=sa.text('auto_receipts = true'), sqlite_where=sa.text('auto_receipts = 1'))


def downgrade():
    raise RuntimeError('Preserve as filas de impressão; reversão exige revisão explícita.')
