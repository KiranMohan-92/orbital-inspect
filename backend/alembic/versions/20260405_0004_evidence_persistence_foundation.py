"""add evidence persistence foundation tables

Revision ID: 20260405_0004
Revises: 20260404_0003
Create Date: 2026-04-05
"""

from alembic import op
import sqlalchemy as sa


revision = "20260405_0004"
down_revision = "20260404_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "asset_reference_profiles",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("asset_id", sa.String(length=32), sa.ForeignKey("assets.id"), nullable=False, unique=True),
        sa.Column("org_id", sa.String(length=32), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("operator_name", sa.String(length=255), nullable=True),
        sa.Column("manufacturer", sa.String(length=255), nullable=True),
        sa.Column("mission_class", sa.String(length=100), nullable=True),
        sa.Column("orbit_regime", sa.String(length=50), nullable=True),
        sa.Column("reference_revision", sa.String(length=64), nullable=True),
        sa.Column("dimensions_json", sa.JSON(), server_default=sa.text("'{}'")),
        sa.Column("subsystem_baseline_json", sa.JSON(), server_default=sa.text("'{}'")),
        sa.Column("reference_sources_json", sa.JSON(), server_default=sa.text("'[]'")),
        sa.Column("last_verified_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_asset_reference_profiles_asset", "asset_reference_profiles", ["asset_id"])
    op.create_index("ix_asset_reference_profiles_org_asset", "asset_reference_profiles", ["org_id", "asset_id"])

    op.create_table(
        "evidence_records",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("org_id", sa.String(length=32), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("asset_id", sa.String(length=32), sa.ForeignKey("assets.id"), nullable=True),
        sa.Column("subsystem_id", sa.String(length=32), sa.ForeignKey("asset_subsystems.id"), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("evidence_role", sa.String(length=32), server_default="runtime"),
        sa.Column("provider", sa.String(length=100), nullable=True),
        sa.Column("external_ref", sa.String(length=255), nullable=True),
        sa.Column("captured_at", sa.DateTime(), nullable=True),
        sa.Column("ingested_at", sa.DateTime(), nullable=True),
        sa.Column("payload_json", sa.JSON(), server_default=sa.text("'{}'")),
        sa.Column("artifact_uri", sa.String(length=500), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("license", sa.String(length=255), nullable=True),
        sa.Column("redistribution_policy", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("geometry_metadata", sa.JSON(), server_default=sa.text("'{}'")),
        sa.Column("tags", sa.JSON(), server_default=sa.text("'[]'")),
    )
    op.create_index("ix_evidence_records_org_asset", "evidence_records", ["org_id", "asset_id"])
    op.create_index("ix_evidence_records_source_role", "evidence_records", ["source_type", "evidence_role"])
    op.create_index("ix_evidence_records_external_ref", "evidence_records", ["external_ref"])
    op.create_index("ix_evidence_records_captured", "evidence_records", ["captured_at"])

    op.create_table(
        "analysis_evidence_links",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("analysis_id", sa.String(length=32), sa.ForeignKey("analyses.id"), nullable=False),
        sa.Column("evidence_id", sa.String(length=32), sa.ForeignKey("evidence_records.id"), nullable=False),
        sa.Column("used_for", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_analysis_evidence_links_analysis", "analysis_evidence_links", ["analysis_id"])
    op.create_index("ix_analysis_evidence_links_evidence", "analysis_evidence_links", ["evidence_id"])
    op.create_index(
        "ix_analysis_evidence_links_unique",
        "analysis_evidence_links",
        ["analysis_id", "evidence_id", "used_for"],
    )

    op.create_table(
        "ingest_runs",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("org_id", sa.String(length=32), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="started"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("records_created", sa.Integer(), server_default="0"),
        sa.Column("records_updated", sa.Integer(), server_default="0"),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("cursor_or_checkpoint", sa.Text(), nullable=True),
        sa.Column("rate_limit_window", sa.String(length=100), nullable=True),
    )
    op.create_index("ix_ingest_runs_source_status", "ingest_runs", ["source_type", "status"])
    op.create_index("ix_ingest_runs_org_started", "ingest_runs", ["org_id", "started_at"])

    op.create_table(
        "dataset_registry",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("org_id", sa.String(length=32), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("dataset_type", sa.String(length=50), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("license", sa.String(length=255), nullable=True),
        sa.Column("intended_use", sa.String(length=50), server_default="offline_eval"),
        sa.Column("local_storage_uri", sa.String(length=500), nullable=True),
        sa.Column("version", sa.String(length=64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_dataset_registry_type", "dataset_registry", ["dataset_type"])
    op.create_index("ix_dataset_registry_org_name", "dataset_registry", ["org_id", "name"])


def downgrade() -> None:
    op.drop_index("ix_dataset_registry_org_name", table_name="dataset_registry")
    op.drop_index("ix_dataset_registry_type", table_name="dataset_registry")
    op.drop_table("dataset_registry")

    op.drop_index("ix_ingest_runs_org_started", table_name="ingest_runs")
    op.drop_index("ix_ingest_runs_source_status", table_name="ingest_runs")
    op.drop_table("ingest_runs")

    op.drop_index("ix_analysis_evidence_links_unique", table_name="analysis_evidence_links")
    op.drop_index("ix_analysis_evidence_links_evidence", table_name="analysis_evidence_links")
    op.drop_index("ix_analysis_evidence_links_analysis", table_name="analysis_evidence_links")
    op.drop_table("analysis_evidence_links")

    op.drop_index("ix_evidence_records_captured", table_name="evidence_records")
    op.drop_index("ix_evidence_records_external_ref", table_name="evidence_records")
    op.drop_index("ix_evidence_records_source_role", table_name="evidence_records")
    op.drop_index("ix_evidence_records_org_asset", table_name="evidence_records")
    op.drop_table("evidence_records")

    op.drop_index("ix_asset_reference_profiles_org_asset", table_name="asset_reference_profiles")
    op.drop_index("ix_asset_reference_profiles_asset", table_name="asset_reference_profiles")
    op.drop_table("asset_reference_profiles")
