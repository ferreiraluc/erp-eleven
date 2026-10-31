"""Isolated WhatsApp Web transport and recoverable outbox claims."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "y7h8i9j0k1l2"
down_revision = "w5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("assistant_whatsapp_bridges",
        sa.Column("id", sa.String(20), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("allow_private", sa.Boolean(), nullable=False),
        sa.Column("notify_tracking", sa.Boolean(), nullable=False),
        sa.Column("group_mode", sa.String(20), nullable=False),
        sa.Column("allowed_groups", postgresql.JSONB(), nullable=False),
        sa.Column("discovered_groups", postgresql.JSONB(), nullable=False),
        sa.Column("token_hash", sa.String(64), unique=True),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("session_generation", sa.Integer(), nullable=False),
        sa.Column("account_phone", sa.String(30)),
        sa.Column("agent_version", sa.String(40)),
        sa.Column("error_code", sa.String(80)),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("pairing_qr", sa.Text()),
        sa.Column("pairing_qr_hash", sa.String(64)),
        sa.Column("pairing_expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.add_column("assistant_deliveries", sa.Column("bridge_claim_key", postgresql.UUID(as_uuid=True)))
    op.add_column("assistant_deliveries", sa.Column("bridge_id", sa.String(20)))
    op.create_unique_constraint("uq_assistant_delivery_bridge_claim", "assistant_deliveries", ["bridge_claim_key"])
    op.create_foreign_key("fk_assistant_delivery_bridge", "assistant_deliveries", "assistant_whatsapp_bridges", ["bridge_id"], ["id"])
    op.create_table("assistant_whatsapp_media",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("conversation_id", sa.String(120), nullable=False),
        sa.Column("message_external_id", sa.String(120), nullable=False, unique=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_assistant_whatsapp_media_user_id", "assistant_whatsapp_media", ["user_id"])
    op.create_index("ix_assistant_whatsapp_media_expires_at", "assistant_whatsapp_media", ["expires_at"])


def downgrade():
    raise RuntimeError("Preserve assistant delivery history; use a forward migration.")
