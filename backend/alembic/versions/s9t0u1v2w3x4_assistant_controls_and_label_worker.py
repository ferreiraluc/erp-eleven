"""Interactive confirmations, persistent knowledge and asynchronous label recovery."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
revision = 's9t0u1v2w3x4'
down_revision = 'r8s9t0u1v2w3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('freight_webhooks',
        sa.Column('environment',sa.String(16),primary_key=True),
        sa.Column('provider_id',sa.String(100),nullable=False),
        sa.Column('url',sa.String(500),nullable=False),
        sa.Column('secret_encrypted',sa.String(2000),nullable=False))
    op.add_column('assistant_deliveries', sa.Column('reply_markup', JSONB()))
    op.add_column('assistant_deliveries', sa.Column('document_pdf', sa.LargeBinary()))
    op.create_table('assistant_knowledge',
        sa.Column('key', sa.String(160), primary_key=True),
        sa.Column('kind', sa.String(30), nullable=False),
        sa.Column('data', JSONB(), nullable=False),
        sa.Column('updated_by', UUID(as_uuid=True), sa.ForeignKey('usuarios.id')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_assistant_knowledge_kind', 'assistant_knowledge', ['kind'])
    for column in [
        sa.Column('label_pdf', sa.LargeBinary()),
        sa.Column('label_status', sa.String(20), nullable=False, server_default='none'),
        sa.Column('label_attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('label_check_at', sa.DateTime(timezone=True)),
        sa.Column('label_error', sa.String(200)),
        sa.Column('auto_print', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('print_device_id', UUID(as_uuid=True), sa.ForeignKey('print_devices.id')),
        sa.Column('print_job_id', UUID(as_uuid=True), sa.ForeignKey('print_jobs.id')),
        sa.Column('notify_channel', sa.String(16)),
        sa.Column('notify_destination', sa.String(120)),
    ]:
        op.add_column('freight_orders', column)
    op.create_index('ix_freight_orders_label_check_at', 'freight_orders', ['label_check_at'])
    op.execute("""UPDATE freight_orders f SET notify_channel=m.channel, notify_destination=m.conversation_id
        FROM assistant_messages m WHERE m.id=f.request_key AND m.channel='telegram'
        AND f.state IN ('released','posted','delivered') AND f.label_url IS NULL""")
    # Recover existing paid PDFs without retroactively scheduling a physical print.
    op.execute("UPDATE freight_orders SET label_status='waiting', label_check_at=now() WHERE state IN ('released','posted','delivered')")


def downgrade():
    op.drop_table('freight_webhooks')
    op.drop_index('ix_freight_orders_label_check_at', table_name='freight_orders')
    for name in ['notify_destination','notify_channel','print_job_id','print_device_id','auto_print','label_error','label_check_at','label_attempts','label_status','label_pdf']:
        op.drop_column('freight_orders', name)
    op.drop_table('assistant_knowledge')
    op.drop_column('assistant_deliveries','document_pdf')
    op.drop_column('assistant_deliveries','reply_markup')
