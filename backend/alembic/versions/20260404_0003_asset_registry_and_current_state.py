"""add asset registry aliases, subsystems, and current-state projection

Revision ID: 20260404_0003
Revises: 20260404_0002
Create Date: 2026-04-04
"""

from alembic import op
import sqlalchemy as sa


revision = "20260404_0003"
down_revision = "20260404_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    op.add_column("assets", sa.Column("external_asset_id", sa.String(length=255), nullable=True))
    op.add_column("assets", sa.Column("identity_source", sa.String(length=32), server_default="norad"))
    op.add_column("assets", sa.Column("current_analysis_id", sa.String(length=32), nullable=True))
    op.create_index("ix_assets_org_external_type", "assets", ["org_id", "external_asset_id", "asset_type"])

    op.create_table(
        "asset_aliases",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("asset_id", sa.String(length=32), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("org_id", sa.String(length=32), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("alias_type", sa.String(length=32), nullable=False),
        sa.Column("alias_value", sa.String(length=255), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("0"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_asset_aliases_org_type_value", "asset_aliases", ["org_id", "alias_type", "alias_value"])
    op.create_index("ix_asset_aliases_asset", "asset_aliases", ["asset_id"])

    op.create_table(
        "asset_subsystems",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("asset_id", sa.String(length=32), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("org_id", sa.String(length=32), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("subsystem_key", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("subsystem_type", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_asset_subsystems_asset_key", "asset_subsystems", ["asset_id", "subsystem_key"])
    op.create_index("ix_asset_subsystems_org_asset", "asset_subsystems", ["org_id", "asset_id"])

    op.add_column("analyses", sa.Column("subsystem_id", sa.String(length=32), nullable=True))

    if not is_sqlite:
        op.create_foreign_key("fk_assets_current_analysis_id", "assets", "analyses", ["current_analysis_id"], ["id"])
        op.create_foreign_key("fk_analyses_subsystem_id", "analyses", "asset_subsystems", ["subsystem_id"], ["id"])


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    if not is_sqlite:
        op.drop_constraint("fk_analyses_subsystem_id", "analyses", type_="foreignkey")
        op.drop_constraint("fk_assets_current_analysis_id", "assets", type_="foreignkey")

    op.drop_column("analyses", "subsystem_id")

    op.drop_index("ix_asset_subsystems_org_asset", table_name="asset_subsystems")
    op.drop_index("ix_asset_subsystems_asset_key", table_name="asset_subsystems")
    op.drop_table("asset_subsystems")

    op.drop_index("ix_asset_aliases_asset", table_name="asset_aliases")
    op.drop_index("ix_asset_aliases_org_type_value", table_name="asset_aliases")
    op.drop_table("asset_aliases")

    op.drop_index("ix_assets_org_external_type", table_name="assets")
    op.drop_column("assets", "current_analysis_id")
    op.drop_column("assets", "identity_source")
    op.drop_column("assets", "external_asset_id")
