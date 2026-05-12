"""deliverable readiness role

Revision ID: c4a9f1e2b8d3
Revises: 7c1a0c8e3a21
Create Date: 2026-05-12 14:45:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "c4a9f1e2b8d3"
down_revision = "7c1a0c8e3a21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not _has_column("deliverables", "ready_to_publish_by_role"):
        op.add_column("deliverables", sa.Column("ready_to_publish_by_role", sa.String(length=32), nullable=True))


def downgrade() -> None:
    if _has_column("deliverables", "ready_to_publish_by_role"):
        op.drop_column("deliverables", "ready_to_publish_by_role")


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    return column_name in {column["name"] for column in inspect(bind).get_columns(table_name)}
