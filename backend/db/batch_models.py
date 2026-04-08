"""
SQLAlchemy ORM model for batch analysis jobs.

Tracks fleet-scan or metadata-only reanalysis batches submitted via the batch API.
"""

import uuid
from sqlalchemy import Column, String, Integer, JSON, DateTime, func
from db.base import Base


class BatchJob(Base):
    """A batch of analysis jobs submitted together for fleet scanning or reanalysis."""

    __tablename__ = "batch_jobs"

    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    org_id = Column(String(32), nullable=True)  # multi-tenant
    status = Column(String(32), default="pending")  # pending|running|completed|partial_failure|failed
    total_items = Column(Integer, nullable=False)
    completed_items = Column(Integer, default=0)
    failed_items = Column(Integer, default=0)
    item_analysis_ids = Column(JSON, default=list)  # list of analysis IDs created
    item_errors = Column(JSON, default=list)  # list of {index, error} for failed items
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)
