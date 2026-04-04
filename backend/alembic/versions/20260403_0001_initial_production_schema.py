"""initial production schema

Revision ID: 20260403_0001
Revises:
Create Date: 2026-04-03
"""

from alembic import op
import sqlalchemy as sa


revision = "20260403_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("tier", sa.String(length=50), server_default="standard"),
        sa.Column("api_key_hash", sa.String(length=128), nullable=True),
        sa.Column("rate_limit_per_hour", sa.Integer(), server_default="50"),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "analyses",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("org_id", sa.String(length=32), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="queued"),
        sa.Column("image_hash", sa.String(length=64), nullable=True),
        sa.Column("image_path", sa.String(length=500), nullable=True),
        sa.Column("norad_id", sa.String(length=9), nullable=True),
        sa.Column("additional_context", sa.Text(), server_default=""),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("asset_type", sa.String(length=50), server_default="satellite"),
        sa.Column("inspection_epoch", sa.String(length=64), nullable=True),
        sa.Column("target_subsystem", sa.String(length=100), nullable=True),
        sa.Column("capture_metadata", sa.JSON(), server_default=sa.text("'{}'")),
        sa.Column("telemetry_summary", sa.JSON(), server_default=sa.text("'{}'")),
        sa.Column("baseline_reference", sa.JSON(), server_default=sa.text("'{}'")),
        sa.Column("classification_result", sa.JSON(), nullable=True),
        sa.Column("vision_result", sa.JSON(), nullable=True),
        sa.Column("environment_result", sa.JSON(), nullable=True),
        sa.Column("failure_mode_result", sa.JSON(), nullable=True),
        sa.Column("insurance_risk_result", sa.JSON(), nullable=True),
        sa.Column("degraded", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("failure_reasons", sa.JSON(), server_default=sa.text("'[]'")),
        sa.Column("evidence_gaps", sa.JSON(), server_default=sa.text("'[]'")),
        sa.Column("report_completeness", sa.String(length=20), server_default="COMPLETE"),
        sa.Column("evidence_completeness_pct", sa.Float(), nullable=True),
        sa.Column("evidence_bundle_summary", sa.JSON(), server_default=sa.text("'{}'")),
        sa.Column("total_cost_usd", sa.Float(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("queue_job_id", sa.String(length=64), nullable=True),
        sa.Column("queue_name", sa.String(length=128), server_default="arq:queue"),
        sa.Column("dispatch_mode", sa.String(length=20), server_default="inline"),
        sa.Column("retry_count", sa.Integer(), server_default="0"),
        sa.Column("max_retries", sa.Integer(), server_default="3"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_retry_at", sa.DateTime(), nullable=True),
        sa.Column("governance_policy_version", sa.String(length=32), server_default="2026-04-03"),
        sa.Column("model_manifest", sa.JSON(), server_default=sa.text("'{}'")),
        sa.Column("human_review_required", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("decision_blocked_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("queued_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_analyses_org_status", "analyses", ["org_id", "status"])
    op.create_index("ix_analyses_queue_job", "analyses", ["queue_job_id"])
    op.create_index("ix_analyses_created", "analyses", ["created_at"])

    op.create_table(
        "analysis_events",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("analysis_id", sa.String(length=32), sa.ForeignKey("analyses.id"), nullable=False),
        sa.Column("agent", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("payload", sa.JSON(), server_default=sa.text("'{}'")),
        sa.Column("sequence", sa.Integer(), server_default="0"),
        sa.Column("degraded", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_events_analysis_seq", "analysis_events", ["analysis_id", "sequence"])

    op.create_table(
        "reports",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("analysis_id", sa.String(length=32), sa.ForeignKey("analyses.id"), nullable=False, unique=True),
        sa.Column("status", sa.String(length=20), server_default="DRAFT"),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column("full_report_json", sa.JSON(), nullable=True),
        sa.Column("pdf_path", sa.String(length=500), nullable=True),
        sa.Column("artifact_path", sa.String(length=500), nullable=True),
        sa.Column("artifact_kind", sa.String(length=20), nullable=True),
        sa.Column("artifact_content_type", sa.String(length=100), nullable=True),
        sa.Column("artifact_size_bytes", sa.Integer(), nullable=True),
        sa.Column("artifact_checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("retention_until", sa.DateTime(), nullable=True),
        sa.Column("governance_summary", sa.JSON(), server_default=sa.text("'{}'")),
        sa.Column("human_review_required", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("submitted_by", sa.String(length=255), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("approved_by", sa.String(length=255), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("reviewer_comments", sa.JSON(), server_default=sa.text("'[]'")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_reports_status", "reports", ["status"])

    op.create_table(
        "dead_letter_jobs",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("analysis_id", sa.String(length=32), sa.ForeignKey("analyses.id"), nullable=False),
        sa.Column("job_id", sa.String(length=64), nullable=True),
        sa.Column("queue_name", sa.String(length=128), server_default="arq:queue"),
        sa.Column("job_name", sa.String(length=128), server_default="run_analysis_job"),
        sa.Column("attempts", sa.Integer(), server_default="1"),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.JSON(), server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_dead_letters_analysis", "dead_letter_jobs", ["analysis_id"])
    op.create_index("ix_dead_letters_created", "dead_letter_jobs", ["created_at"])

    op.create_table(
        "webhook_endpoints",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("org_id", sa.String(length=32), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("secret_hash", sa.String(length=128), server_default=""),
        sa.Column("secret_ciphertext", sa.Text(), server_default=""),
        sa.Column("events", sa.JSON(), server_default=sa.text("'[]'")),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_webhooks_org_active", "webhook_endpoints", ["org_id", "active"])

    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("webhook_id", sa.String(length=32), sa.ForeignKey("webhook_endpoints.id"), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("success", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default="1"),
        sa.Column("response_excerpt", sa.Text(), nullable=True),
        sa.Column("request_body_checksum", sa.String(length=64), nullable=True),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_webhook_deliveries_webhook", "webhook_deliveries", ["webhook_id", "created_at"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("org_id", sa.String(length=32), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("actor_id", sa.String(length=255), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=False),
        sa.Column("resource_id", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), server_default=sa.text("'{}'")),
        sa.Column("analysis_id", sa.String(length=32), sa.ForeignKey("analyses.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_audit_logs_org_created", "audit_logs", ["org_id", "created_at"])
    op.create_index("ix_audit_logs_resource", "audit_logs", ["resource_type", "resource_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_resource", table_name="audit_logs")
    op.drop_index("ix_audit_logs_org_created", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_webhook_deliveries_webhook", table_name="webhook_deliveries")
    op.drop_table("webhook_deliveries")
    op.drop_index("ix_webhooks_org_active", table_name="webhook_endpoints")
    op.drop_table("webhook_endpoints")
    op.drop_index("ix_dead_letters_created", table_name="dead_letter_jobs")
    op.drop_index("ix_dead_letters_analysis", table_name="dead_letter_jobs")
    op.drop_table("dead_letter_jobs")
    op.drop_index("ix_reports_status", table_name="reports")
    op.drop_table("reports")
    op.drop_index("ix_events_analysis_seq", table_name="analysis_events")
    op.drop_table("analysis_events")
    op.drop_index("ix_analyses_created", table_name="analyses")
    op.drop_index("ix_analyses_queue_job", table_name="analyses")
    op.drop_index("ix_analyses_org_status", table_name="analyses")
    op.drop_table("analyses")
    op.drop_table("organizations")
