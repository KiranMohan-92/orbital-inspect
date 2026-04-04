"""
SQLAlchemy ORM models for persistent storage.

Tables:
  - organizations: Multi-tenant org records
  - analyses: Satellite inspection jobs
  - analysis_events: SSE events per analysis (audit trail)
  - reports: Finalized condition reports with approval workflow
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, Boolean, Float, Integer, DateTime,
    ForeignKey, JSON, Index,
)
from sqlalchemy.orm import relationship
from db.base import Base


def _uuid() -> str:
    return uuid.uuid4().hex


class Organization(Base):
    """Multi-tenant organization."""
    __tablename__ = "organizations"

    id = Column(String(32), primary_key=True, default=_uuid)
    name = Column(String(255), nullable=False)
    tier = Column(String(50), default="standard")  # standard | premium | enterprise
    api_key_hash = Column(String(128), nullable=True)
    rate_limit_per_hour = Column(Integer, default=50)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    analyses = relationship("Analysis", back_populates="organization")


class Analysis(Base):
    """A satellite inspection analysis job."""
    __tablename__ = "analyses"
    __table_args__ = (
        Index("ix_analyses_org_status", "org_id", "status"),
        Index("ix_analyses_queue_job", "queue_job_id"),
        Index("ix_analyses_created", "created_at"),
    )

    id = Column(String(32), primary_key=True, default=_uuid)
    org_id = Column(String(32), ForeignKey("organizations.id"), nullable=True)
    status = Column(String(32), default="queued")  # queued | dispatched | running | retrying | completed | completed_partial | failed | rejected

    # Input
    image_hash = Column(String(64), nullable=True)  # SHA-256 of uploaded image
    image_path = Column(String(500), nullable=True)  # Storage URI for uploaded image
    norad_id = Column(String(9), nullable=True)
    additional_context = Column(Text, default="")
    request_id = Column(String(64), nullable=True)
    asset_type = Column(String(50), default="satellite")
    inspection_epoch = Column(String(64), nullable=True)
    target_subsystem = Column(String(100), nullable=True)
    capture_metadata = Column(JSON, default=dict)
    telemetry_summary = Column(JSON, default=dict)
    baseline_reference = Column(JSON, default=dict)

    # Results (stored as JSON)
    classification_result = Column(JSON, nullable=True)
    vision_result = Column(JSON, nullable=True)
    environment_result = Column(JSON, nullable=True)
    failure_mode_result = Column(JSON, nullable=True)
    insurance_risk_result = Column(JSON, nullable=True)

    # Metadata
    degraded = Column(Boolean, default=False)
    failure_reasons = Column(JSON, default=list)
    evidence_gaps = Column(JSON, default=list)  # List of failed agent names
    report_completeness = Column(String(20), default="COMPLETE")
    evidence_completeness_pct = Column(Float, nullable=True)
    evidence_bundle_summary = Column(JSON, default=dict)
    total_cost_usd = Column(Float, nullable=True)  # Gemini API cost
    total_tokens = Column(Integer, nullable=True)
    queue_job_id = Column(String(64), nullable=True)
    queue_name = Column(String(128), default="arq:queue")
    dispatch_mode = Column(String(20), default="inline")
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    last_error = Column(Text, nullable=True)
    last_retry_at = Column(DateTime, nullable=True)
    governance_policy_version = Column(String(32), default="2026-04-03")
    model_manifest = Column(JSON, default=dict)
    human_review_required = Column(Boolean, default=True)
    decision_blocked_reason = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    queued_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    organization = relationship("Organization", back_populates="analyses")
    events = relationship("AnalysisEvent", back_populates="analysis", order_by="AnalysisEvent.sequence")
    report = relationship("Report", back_populates="analysis", uselist=False)
    dead_letters = relationship("DeadLetterJob", back_populates="analysis")
    audit_logs = relationship("AuditLog", back_populates="analysis")


class AnalysisEvent(Base):
    """Individual SSE event within an analysis (audit trail)."""
    __tablename__ = "analysis_events"
    __table_args__ = (
        Index("ix_events_analysis_seq", "analysis_id", "sequence"),
    )

    id = Column(String(32), primary_key=True, default=_uuid)
    analysis_id = Column(String(32), ForeignKey("analyses.id"), nullable=False)
    agent = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False)  # queued | thinking | complete | error
    payload = Column(JSON, default=dict)
    sequence = Column(Integer, default=0)
    degraded = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    analysis = relationship("Analysis", back_populates="events")


class Report(Base):
    """Finalized Satellite Condition Report with approval workflow."""
    __tablename__ = "reports"
    __table_args__ = (
        Index("ix_reports_status", "status"),
    )

    id = Column(String(32), primary_key=True, default=_uuid)
    analysis_id = Column(String(32), ForeignKey("analyses.id"), nullable=False, unique=True)

    # Workflow status
    status = Column(String(20), default="DRAFT")  # DRAFT | PENDING_REVIEW | APPROVED | PUBLISHED | REJECTED
    version = Column(Integer, default=1)

    # Content
    full_report_json = Column(JSON, nullable=True)  # Complete SatelliteConditionReport
    pdf_path = Column(String(500), nullable=True)  # Storage URI for generated artifact
    artifact_path = Column(String(500), nullable=True)
    artifact_kind = Column(String(20), nullable=True)  # pdf | html
    artifact_content_type = Column(String(100), nullable=True)
    artifact_size_bytes = Column(Integer, nullable=True)
    artifact_checksum_sha256 = Column(String(64), nullable=True)
    retention_until = Column(DateTime, nullable=True)
    governance_summary = Column(JSON, default=dict)
    human_review_required = Column(Boolean, default=True)
    published_at = Column(DateTime, nullable=True)

    # Approval chain
    submitted_by = Column(String(255), nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    approved_by = Column(String(255), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    reviewer_comments = Column(JSON, default=list)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    analysis = relationship("Analysis", back_populates="report")


class DeadLetterJob(Base):
    """Persisted record of failed analysis jobs after retry exhaustion."""
    __tablename__ = "dead_letter_jobs"
    __table_args__ = (
        Index("ix_dead_letters_analysis", "analysis_id"),
        Index("ix_dead_letters_created", "created_at"),
    )

    id = Column(String(32), primary_key=True, default=_uuid)
    analysis_id = Column(String(32), ForeignKey("analyses.id"), nullable=False)
    job_id = Column(String(64), nullable=True)
    queue_name = Column(String(128), default="arq:queue")
    job_name = Column(String(128), default="run_analysis_job")
    attempts = Column(Integer, default=1)
    error_message = Column(Text, nullable=False)
    payload_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    analysis = relationship("Analysis", back_populates="dead_letters")


class WebhookEndpoint(Base):
    """Persisted webhook endpoint for one organization."""
    __tablename__ = "webhook_endpoints"
    __table_args__ = (
        Index("ix_webhooks_org_active", "org_id", "active"),
    )

    id = Column(String(32), primary_key=True, default=_uuid)
    org_id = Column(String(32), ForeignKey("organizations.id"), nullable=True)
    url = Column(String(500), nullable=False)
    secret_hash = Column(String(128), default="")
    secret_ciphertext = Column(Text, default="")
    events = Column(JSON, default=list)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    deliveries = relationship("WebhookDelivery", back_populates="webhook")


class WebhookDelivery(Base):
    """Delivery log for webhook notifications."""
    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        Index("ix_webhook_deliveries_webhook", "webhook_id", "created_at"),
    )

    id = Column(String(32), primary_key=True, default=_uuid)
    webhook_id = Column(String(32), ForeignKey("webhook_endpoints.id"), nullable=False)
    event_type = Column(String(100), nullable=False)
    success = Column(Boolean, default=False)
    status_code = Column(Integer, nullable=True)
    attempt_count = Column(Integer, default=1)
    response_excerpt = Column(Text, nullable=True)
    request_body_checksum = Column(String(64), nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    webhook = relationship("WebhookEndpoint", back_populates="deliveries")


class AuditLog(Base):
    """Immutable audit log for privileged and lifecycle actions."""
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_org_created", "org_id", "created_at"),
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
    )

    id = Column(String(32), primary_key=True, default=_uuid)
    org_id = Column(String(32), ForeignKey("organizations.id"), nullable=True)
    actor_id = Column(String(255), nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=False)
    resource_id = Column(String(64), nullable=False)
    metadata_json = Column(JSON, default=dict)
    analysis_id = Column(String(32), ForeignKey("analyses.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    analysis = relationship("Analysis", back_populates="audit_logs")
