"""Individual access, revocable sessions and user audit. Existing history is preserved."""
from alembic import op
import sqlalchemy as sa

revision = 'z6a7b8c9d0e1'
down_revision = 'y5z6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('usuarios', sa.Column('auth_version', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('usuarios', sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('usuarios', sa.Column('sales_scope', sa.String(10), nullable=False, server_default='all'))
    op.add_column('usuarios', sa.Column('sales_seller', sa.String(100)))
    op.add_column('usuarios', sa.Column('vendedor_id', sa.Uuid(), sa.ForeignKey('vendedores.id')))
    op.create_index('ix_usuarios_email_lower', 'usuarios', [sa.text('lower(email)')], unique=True)
    op.create_table('auth_sessions',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('usuarios.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True)),
        sa.Column('activity_credit_at', sa.DateTime(timezone=True)))
    op.create_index('ix_auth_sessions_user_id', 'auth_sessions', ['user_id'])
    op.create_table('audit_events',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('usuarios.id')),
        sa.Column('actor_name', sa.String(100), nullable=False),
        sa.Column('source', sa.String(30), nullable=False),
        sa.Column('action', sa.String(40), nullable=False),
        sa.Column('module', sa.String(80), nullable=False),
        sa.Column('entity', sa.String(100)), sa.Column('entity_id', sa.String(100)),
        sa.Column('request_id', sa.String(36)), sa.Column('route', sa.String(200)),
        sa.Column('method', sa.String(10)), sa.Column('status_code', sa.Integer()),
        sa.Column('changes', sa.JSON(), nullable=False))
    for suffix, cols in [('user_id',['user_id']), ('time',['occurred_at']), ('request_id',['request_id'])]:
        op.create_index('ix_audit_events_' + suffix, 'audit_events', cols)
    op.create_table('activity_spans',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('usuarios.id'), nullable=False),
        sa.Column('session_id', sa.Uuid(), sa.ForeignKey('auth_sessions.id'), nullable=False),
        sa.Column('module', sa.String(80), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('active_seconds', sa.Integer(), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False))
    for suffix, cols in [('user_id',['user_id']), ('session_id',['session_id']), ('time',['started_at'])]:
        op.create_index('ix_activity_spans_' + suffix, 'activity_spans', cols)


def downgrade():
    # Audit is operational history: rollback application code, not recorded activity.
    raise RuntimeError('Preserve access/audit history; use a forward migration for schema changes.')
