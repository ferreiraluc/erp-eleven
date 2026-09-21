"""Add multi-channel assistant persistence.

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "n4o5p6q7r8s9"
down_revision = "m3n4o5p6q7r8"
branch_labels = None
depends_on = None


def ident():
    return sa.Column("id", UUID(as_uuid=True), primary_key=True)


def owner(nullable=False):
    return sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=nullable)


def created():
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)


def upgrade():
    op.create_table("assistant_identities", ident(),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("external_id", sa.String(100), nullable=False), owner(),
        sa.Column("active", sa.Boolean, nullable=False),
        sa.Column("can_register", sa.Boolean, nullable=False),
        sa.UniqueConstraint("channel", "external_id", name="uq_assistant_identity"))
    op.create_table("assistant_messages", ident(),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("external_id", sa.String(120), nullable=False),
        sa.Column("conversation_id", sa.String(120), nullable=False),
        sa.Column("sender_id", sa.String(100), nullable=False), owner(),
        sa.Column("text", sa.Text, nullable=False), sa.Column("response", sa.Text),
        sa.Column("should_reply", sa.Boolean, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False),
        sa.Column("error_code", sa.String(80)), created(),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("channel", "external_id", name="uq_assistant_message"))
    op.create_index("ix_assistant_messages_conversation_id", "assistant_messages", ["conversation_id"])
    op.create_index("ix_assistant_messages_status", "assistant_messages", ["status"])
    op.create_table("assistant_notes", ident(),
        sa.Column("source_message_id", UUID(as_uuid=True), sa.ForeignKey("assistant_messages.id"), nullable=False, unique=True),
        owner(), sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=False), created(),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)))
    op.create_index("ix_assistant_notes_status", "assistant_notes", ["status"])
    op.create_table("assistant_deliveries", ident(),
        sa.Column("event_key", sa.String(240), nullable=False, unique=True),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("destination", sa.String(120), nullable=False),
        sa.Column("text", sa.Text, nullable=False), owner(nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False),
        sa.Column("provider_id", sa.String(120)), sa.Column("error_code", sa.String(80)),
        created(), sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)))
    op.create_index("ix_assistant_deliveries_status", "assistant_deliveries", ["status"])


def downgrade():
    for table in ("assistant_deliveries", "assistant_notes", "assistant_messages", "assistant_identities"):
        op.drop_table(table)
