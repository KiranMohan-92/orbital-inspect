"""add asset foundation and decision triage fields

Revision ID: 20260404_0002
Revises: 20260403_0001
Create Date: 2026-04-04
"""

from alembic import op
import sqlalchemy as sa


revision = "20260404_0002"
down_revision = "20260403_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    op.create_table(
        "assets",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("org_id", sa.String(length=32), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("norad_id", sa.String(length=9), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("asset_type", sa.String(length=50), server_default="satellite"),
        sa.Column("operator_name", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_assets_org_norad_type", "assets", ["org_id", "norad_id", "asset_type"])
    op.create_index("ix_assets_org_created", "assets", ["org_id", "created_at"])

    op.add_column("analyses", sa.Column("asset_id", sa.String(length=32), nullable=True))
    op.add_column("analyses", sa.Column("decision_summary", sa.JSON(), server_default=sa.text("'{}'")))
    op.add_column("analyses", sa.Column("decision_status", sa.String(length=32), server_default="pending_policy"))
    op.add_column("analyses", sa.Column("decision_recommended_action", sa.String(length=64), nullable=True))
    op.add_column("analyses", sa.Column("decision_confidence", sa.String(length=32), nullable=True))
    op.add_column("analyses", sa.Column("decision_urgency", sa.String(length=32), nullable=True))
    op.add_column("analyses", sa.Column("decision_approved_by", sa.String(length=255), nullable=True))
    op.add_column("analyses", sa.Column("decision_approved_at", sa.DateTime(), nullable=True))
    op.add_column("analyses", sa.Column("decision_override_reason", sa.Text(), nullable=True))
    op.add_column("analyses", sa.Column("decision_last_evaluated_at", sa.DateTime(), nullable=True))
    op.add_column("analyses", sa.Column("triage_score", sa.Float(), nullable=True))
    op.add_column("analyses", sa.Column("triage_band", sa.String(length=32), nullable=True))
    op.add_column("analyses", sa.Column("triage_factors", sa.JSON(), server_default=sa.text("'{}'")))
    op.add_column("analyses", sa.Column("recurrence_count", sa.Integer(), server_default="0"))
    if not is_sqlite:
        op.create_foreign_key("fk_analyses_asset_id", "analyses", "assets", ["asset_id"], ["id"])


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    if not is_sqlite:
        op.drop_constraint("fk_analyses_asset_id", "analyses", type_="foreignkey")
    op.drop_column("analyses", "recurrence_count")
    op.drop_column("analyses", "triage_factors")
    op.drop_column("analyses", "triage_band")
    op.drop_column("analyses", "triage_score")
    op.drop_column("analyses", "decision_last_evaluated_at")
    op.drop_column("analyses", "decision_override_reason")
    op.drop_column("analyses", "decision_approved_at")
    op.drop_column("analyses", "decision_approved_by")
    op.drop_column("analyses", "decision_urgency")
    op.drop_column("analyses", "decision_confidence")
    op.drop_column("analyses", "decision_recommended_action")
    op.drop_column("analyses", "decision_status")
    op.drop_column("analyses", "decision_summary")
    op.drop_column("analyses", "asset_id")
    op.drop_index("ix_assets_org_created", table_name="assets")
    op.drop_index("ix_assets_org_norad_type", table_name="assets")
    op.drop_table("assets")
