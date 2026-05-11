"""campaign health persistence

Revision ID: 7c1a0c8e3a21
Revises: 219fcb44bea6
Create Date: 2026-05-11 11:40:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7c1a0c8e3a21"
down_revision = "219fcb44bea6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("campaigns", sa.Column("health", sa.String(length=24), nullable=False, server_default="not_started"))
    op.add_column("campaigns", sa.Column("health_reason", sa.String(length=128), nullable=True))
    op.add_column("campaigns", sa.Column("health_updated_at", sa.DateTime(), nullable=True))

    op.create_index("ix_campaigns_created_at", "campaigns", ["created_at"], unique=False)
    op.create_index("ix_campaigns_status_created_at", "campaigns", ["status", "created_at"], unique=False)
    op.create_index("ix_campaigns_deal_id", "campaigns", ["deal_id"], unique=False)
    op.create_index("ix_campaign_assignments_campaign_id", "campaign_assignments", ["campaign_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_campaign_assignments_campaign_id", table_name="campaign_assignments")
    op.drop_index("ix_campaigns_deal_id", table_name="campaigns")
    op.drop_index("ix_campaigns_status_created_at", table_name="campaigns")
    op.drop_index("ix_campaigns_created_at", table_name="campaigns")

    op.drop_column("campaigns", "health_updated_at")
    op.drop_column("campaigns", "health_reason")
    op.drop_column("campaigns", "health")
