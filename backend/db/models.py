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
    ForeignKey, JSON, Enum as SAEnum, Index,
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
        Index("ix_analyses_created", "created_at"),
    )

    id = Column(String(32), primary_key=True, default=_uuid)
    org_id = Column(String(32), ForeignKey("organizations.id"), nullable=True)
    status = Column(String(20), default="queued")  # queued | running | completed | failed

    # Input
    image_hash = Column(String(64), nullable=True)  # SHA-256 of uploaded image
    image_path = Column(String(500), nullable=True)  # Local/S3 path to stored image
    norad_id = Column(String(9), nullable=True)
    additional_context = Column(Text, default="")

    # Results (stored as JSON)
    classification_result = Column(JSON, nullable=True)
    vision_result = Column(JSON, nullable=True)
    environment_result = Column(JSON, nullable=True)
    failure_mode_result = Column(JSON, nullable=True)
    insurance_risk_result = Column(JSON, nullable=True)

    # Metadata
    evidence_gaps = Column(JSON, default=list)  # List of failed agent names
    report_completeness = Column(String(20), default="COMPLETE")
    total_cost_usd = Column(Float, nullable=True)  # Gemini API cost
    total_tokens = Column(Integer, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    organization = relationship("Organization", back_populates="analyses")
    events = relationship("AnalysisEvent", back_populates="analysis", order_by="AnalysisEvent.sequence")
    report = relationship("Report", back_populates="analysis", uselist=False)


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
    pdf_path = Column(String(500), nullable=True)

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
