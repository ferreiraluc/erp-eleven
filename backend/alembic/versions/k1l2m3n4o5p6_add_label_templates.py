"""add label_templates

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-05-04

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'k1l2m3n4o5p6'
down_revision = 'j0k1l2m3n4o5'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'label_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('brand', sa.String(100), nullable=False),
        sa.Column('notes', sa.Text()),
        sa.Column('sample_image', sa.Text()),
        sa.Column('parsed_name', sa.String(200)),
        sa.Column('parsed_size', sa.String(50)),
        sa.Column('parsed_color', sa.String(50)),
        sa.Column('parsed_barcode', sa.String(50)),
        sa.Column('parsed_price', sa.String(30)),
        sa.Column('parsed_currency', sa.String(10)),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('usuarios.id'), nullable=True),
    )
    op.create_index('idx_label_templates_brand', 'label_templates', ['brand'])


def downgrade():
    op.drop_index('idx_label_templates_brand', table_name='label_templates')
    op.drop_table('label_templates')
