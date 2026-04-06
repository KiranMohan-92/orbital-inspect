"""
SQLAlchemy ORM models for persistent storage.

Tables:
  - organizations: Multi-tenant org records
  - assets: Stable orbital asset identities within an org
  - asset_aliases: Canonical and external identifiers for assets
  - asset_subsystems: Stable subsystem identities within an asset
  - asset_reference_profiles: Canonical baseline/reference profiles for assets
  - evidence_records: Reusable evidence collected from external or internal sources
  - analysis_evidence_links: Provenance links from analyses to evidence records
  - ingest_runs: Source-ingestion execution tracking
  - dataset_registry: Offline benchmark dataset registry
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
    assets = relationship("Asset", back_populates="organization")
    evidence_records = relationship("EvidenceRecord", back_populates="organization")
    ingest_runs = relationship("IngestRun", back_populates="organization")
    datasets = relationship("DatasetRegistry", back_populates="organization")


class Asset(Base):
    """Stable identity for an orbital asset inside one organization."""

    __tablename__ = "assets"
    __table_args__ = (
        Index("ix_assets_org_norad_type", "org_id", "norad_id", "asset_type"),
        Index("ix_assets_org_external_type", "org_id", "external_asset_id", "asset_type"),
        Index("ix_assets_org_created", "org_id", "created_at"),
    )

    id = Column(String(32), primary_key=True, default=_uuid)
    org_id = Column(String(32), ForeignKey("organizations.id"), nullable=True)
    norad_id = Column(String(9), nullable=True)
    external_asset_id = Column(String(255), nullable=True)
    name = Column(String(255), nullable=True)
    asset_type = Column(String(50), default="satellite")
    identity_source = Column(String(32), default="norad")  # norad | external_id | label | ephemeral
    operator_name = Column(String(255), nullable=True)
    status = Column(String(32), default="active")
    current_analysis_id = Column(String(32), ForeignKey("analyses.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    organization = relationship("Organization", back_populates="assets")
    analyses = relationship("Analysis", back_populates="asset", foreign_keys="Analysis.asset_id")
    aliases = relationship("AssetAlias", back_populates="asset", cascade="all, delete-orphan")
    subsystems = relationship("AssetSubsystem", back_populates="asset", cascade="all, delete-orphan")
    evidence_records = relationship("EvidenceRecord", back_populates="asset", cascade="all, delete-orphan")
    reference_profile = relationship(
        "AssetReferenceProfile",
        back_populates="asset",
        uselist=False,
        cascade="all, delete-orphan",
    )
    current_analysis = relationship("Analysis", foreign_keys=[current_analysis_id], post_update=True)


class AssetAlias(Base):
    """Alternate identifiers for canonical asset records."""

    __tablename__ = "asset_aliases"
    __table_args__ = (
        Index("ix_asset_aliases_org_type_value", "org_id", "alias_type", "alias_value"),
        Index("ix_asset_aliases_asset", "asset_id"),
    )

    id = Column(String(32), primary_key=True, default=_uuid)
    asset_id = Column(String(32), ForeignKey("assets.id"), nullable=False)
    org_id = Column(String(32), ForeignKey("organizations.id"), nullable=True)
    alias_type = Column(String(32), nullable=False)  # norad | external_id | display_name | operator_label
    alias_value = Column(String(255), nullable=False)
    is_primary = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    asset = relationship("Asset", back_populates="aliases")


class AssetSubsystem(Base):
    """Stable subsystem identity under a canonical asset."""

    __tablename__ = "asset_subsystems"
    __table_args__ = (
        Index("ix_asset_subsystems_asset_key", "asset_id", "subsystem_key"),
        Index("ix_asset_subsystems_org_asset", "org_id", "asset_id"),
    )

    id = Column(String(32), primary_key=True, default=_uuid)
    asset_id = Column(String(32), ForeignKey("assets.id"), nullable=False)
    org_id = Column(String(32), ForeignKey("organizations.id"), nullable=True)
    subsystem_key = Column(String(100), nullable=False)
    display_name = Column(String(255), nullable=True)
    subsystem_type = Column(String(100), nullable=True)
    status = Column(String(32), default="active")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


    asset = relationship("Asset", back_populates="subsystems")
    analyses = relationship("Analysis", back_populates="subsystem")
    evidence_records = relationship("EvidenceRecord", back_populates="subsystem")


class AssetReferenceProfile(Base):
    """Canonical baseline/reference profile for one asset."""

    __tablename__ = "asset_reference_profiles"
    __table_args__ = (
        Index("ix_asset_reference_profiles_asset", "asset_id"),
        Index("ix_asset_reference_profiles_org_asset", "org_id", "asset_id"),
    )

    id = Column(String(32), primary_key=True, default=_uuid)
    asset_id = Column(String(32), ForeignKey("assets.id"), nullable=False, unique=True)
    org_id = Column(String(32), ForeignKey("organizations.id"), nullable=True)
    operator_name = Column(String(255), nullable=True)
    manufacturer = Column(String(255), nullable=True)
    mission_class = Column(String(100), nullable=True)
    orbit_regime = Column(String(50), nullable=True)
    reference_revision = Column(String(64), nullable=True)
    dimensions_json = Column(JSON, default=dict)
    subsystem_baseline_json = Column(JSON, default=dict)
    reference_sources_json = Column(JSON, default=list)
    last_verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    asset = relationship("Asset", back_populates="reference_profile")


class EvidenceRecord(Base):
    """Reusable evidence persisted independently of a single analysis."""

    __tablename__ = "evidence_records"
    __table_args__ = (
        Index("ix_evidence_records_org_asset", "org_id", "asset_id"),
        Index("ix_evidence_records_source_role", "source_type", "evidence_role"),
        Index("ix_evidence_records_external_ref", "external_ref"),
        Index("ix_evidence_records_captured", "captured_at"),
    )

    id = Column(String(32), primary_key=True, default=_uuid)
    org_id = Column(String(32), ForeignKey("organizations.id"), nullable=True)
    asset_id = Column(String(32), ForeignKey("assets.id"), nullable=True)
    subsystem_id = Column(String(32), ForeignKey("asset_subsystems.id"), nullable=True)
    source_type = Column(String(50), nullable=False)
    evidence_role = Column(String(32), default="runtime")
    provider = Column(String(100), nullable=True)
    external_ref = Column(String(255), nullable=True)
    captured_at = Column(DateTime, nullable=True)
    ingested_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    payload_json = Column(JSON, default=dict)
    artifact_uri = Column(String(500), nullable=True)
    source_url = Column(String(1000), nullable=True)
    license = Column(String(255), nullable=True)
    redistribution_policy = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    geometry_metadata = Column(JSON, default=dict)
    tags = Column(JSON, default=list)

    organization = relationship("Organization", back_populates="evidence_records")
    asset = relationship("Asset", back_populates="evidence_records")
    subsystem = relationship("AssetSubsystem", back_populates="evidence_records")
    analysis_links = relationship(
        "AnalysisEvidenceLink",
        back_populates="evidence_record",
        cascade="all, delete-orphan",
    )


class AnalysisEvidenceLink(Base):
    """Link table preserving which evidence records informed one analysis."""

    __tablename__ = "analysis_evidence_links"
    __table_args__ = (
        Index("ix_analysis_evidence_links_analysis", "analysis_id"),
        Index("ix_analysis_evidence_links_evidence", "evidence_id"),
        Index("ix_analysis_evidence_links_unique", "analysis_id", "evidence_id", "used_for"),
    )

    id = Column(String(32), primary_key=True, default=_uuid)
    analysis_id = Column(String(32), ForeignKey("analyses.id"), nullable=False)
    evidence_id = Column(String(32), ForeignKey("evidence_records.id"), nullable=False)
    used_for = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    analysis = relationship("Analysis", back_populates="evidence_links")
    evidence_record = relationship("EvidenceRecord", back_populates="analysis_links")


class IngestRun(Base):
    """Tracks one source-ingestion run and its checkpoint/summary."""

    __tablename__ = "ingest_runs"
    __table_args__ = (
        Index("ix_ingest_runs_source_status", "source_type", "status"),
        Index("ix_ingest_runs_org_started", "org_id", "started_at"),
    )

    id = Column(String(32), primary_key=True, default=_uuid)
    org_id = Column(String(32), ForeignKey("organizations.id"), nullable=True)
    source_type = Column(String(50), nullable=False)
    status = Column(String(32), default="started")
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    records_created = Column(Integer, default=0)
    records_updated = Column(Integer, default=0)
    error_summary = Column(Text, nullable=True)
    cursor_or_checkpoint = Column(Text, nullable=True)
    rate_limit_window = Column(String(100), nullable=True)

    organization = relationship("Organization", back_populates="ingest_runs")


class DatasetRegistry(Base):
    """Metadata for offline benchmark datasets used in evaluation/R&D."""

    __tablename__ = "dataset_registry"
    __table_args__ = (
        Index("ix_dataset_registry_type", "dataset_type"),
        Index("ix_dataset_registry_org_name", "org_id", "name"),
    )

    id = Column(String(32), primary_key=True, default=_uuid)
    org_id = Column(String(32), ForeignKey("organizations.id"), nullable=True)
    name = Column(String(255), nullable=False)
    dataset_type = Column(String(50), nullable=False)
    source_url = Column(String(1000), nullable=False)
    license = Column(String(255), nullable=True)
    intended_use = Column(String(50), default="offline_eval")
    local_storage_uri = Column(String(500), nullable=True)
    version = Column(String(64), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    organization = relationship("Organization", back_populates="datasets")


class Analysis(Base):
    """A satellite inspection analysis job."""
    __tablename__ = "analyses"
    __table_args__ = (
        Index("ix_analyses_org_status", "org_id", "status"),
        Index("ix_analyses_asset_completed", "asset_id", "completed_at"),
        Index("ix_analyses_asset_subsystem", "asset_id", "subsystem_id"),
        Index("ix_analyses_queue_job", "queue_job_id"),
        Index("ix_analyses_created", "created_at"),
    )

    id = Column(String(32), primary_key=True, default=_uuid)
    org_id = Column(String(32), ForeignKey("organizations.id"), nullable=True)
    asset_id = Column(String(32), ForeignKey("assets.id"), nullable=True)
    subsystem_id = Column(String(32), ForeignKey("asset_subsystems.id"), nullable=True)
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
    decision_summary = Column(JSON, default=dict)
    decision_status = Column(String(32), default="pending_policy")
    decision_recommended_action = Column(String(64), nullable=True)
    decision_confidence = Column(String(32), nullable=True)
    decision_urgency = Column(String(32), nullable=True)
    decision_approved_by = Column(String(255), nullable=True)
    decision_approved_at = Column(DateTime, nullable=True)
    decision_override_reason = Column(Text, nullable=True)
    decision_last_evaluated_at = Column(DateTime, nullable=True)
    triage_score = Column(Float, nullable=True)
    triage_band = Column(String(32), nullable=True)
    triage_factors = Column(JSON, default=dict)
    recurrence_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    queued_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    organization = relationship("Organization", back_populates="analyses")
    asset = relationship("Asset", back_populates="analyses", foreign_keys=[asset_id])
    subsystem = relationship("AssetSubsystem", back_populates="analyses")
    evidence_links = relationship(
        "AnalysisEvidenceLink",
        back_populates="analysis",
        cascade="all, delete-orphan",
    )
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
