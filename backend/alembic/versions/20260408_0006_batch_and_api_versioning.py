"""Add batch_jobs table for fleet-scale batch analysis.

Revision ID: 20260408_0006
Revises: 20260407_0005
Create Date: 2026-04-08

Adds the batch_jobs table to support fleet-scale batch analysis submissions
via the POST /api/v1/batch/analyses endpoint.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260408_0006"
down_revision = "20260407_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "batch_jobs",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("org_id", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="pending"),
        sa.Column("total_items", sa.Integer(), nullable=False),
        sa.Column("completed_items", sa.Integer(), server_default="0"),
        sa.Column("failed_items", sa.Integer(), server_default="0"),
        sa.Column("item_analysis_ids", sa.JSON(), server_default="[]"),
        sa.Column("item_errors", sa.JSON(), server_default="[]"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_batch_jobs_org_id", "batch_jobs", ["org_id"])
    op.create_index("ix_batch_jobs_status", "batch_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_batch_jobs_status", table_name="batch_jobs")
    op.drop_index("ix_batch_jobs_org_id", table_name="batch_jobs")
    op.drop_table("batch_jobs")
