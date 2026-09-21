"""Confirmed ERP actions and ordered multipart assistant replies.

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "o5p6q7r8s9t0"
down_revision = "n4o5p6q7r8s9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("assistant_deliveries", sa.Column("depends_on_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_assistant_delivery_predecessor", "assistant_deliveries", "assistant_deliveries", ["depends_on_id"], ["id"])
    op.create_table("assistant_actions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("source_message_id", UUID(as_uuid=True), sa.ForeignKey("assistant_messages.id"), nullable=False, unique=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("result_id", UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True)))
    op.create_index("ix_assistant_actions_status", "assistant_actions", ["status"])


def downgrade():
    op.drop_table("assistant_actions")
    op.drop_constraint("fk_assistant_delivery_predecessor", "assistant_deliveries", type_="foreignkey")
    op.drop_column("assistant_deliveries", "depends_on_id")
