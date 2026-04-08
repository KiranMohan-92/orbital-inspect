"""Add fleet performance indexes for portfolio queries at scale.

Revision ID: 20260408_0007
Revises: 20260408_0006
Create Date: 2026-04-08

Adds indexes on assets.current_analysis_id and (org_id, norad_id) to
support sub-second portfolio queries and fleet ingestion at 6,000+ assets.
"""

from alembic import op

revision = "20260408_0007"
down_revision = "20260408_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_assets_current_analysis", "assets", ["current_analysis_id"])
    op.create_index("ix_assets_org_norad_fleet", "assets", ["org_id", "norad_id"])


def downgrade() -> None:
    op.drop_index("ix_assets_org_norad_fleet", table_name="assets")
    op.drop_index("ix_assets_current_analysis", table_name="assets")
