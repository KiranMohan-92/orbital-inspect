"""
Evidence fusion models for multi-source satellite intelligence.

Evidence sources include imagery, telemetry, TLE orbital history,
operator maintenance records, and prior analysis results.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone
from enum import Enum


class EvidenceSource(str, Enum):
    """Types of evidence that can be fused into an analysis."""
    IMAGERY = "imagery"
    TELEMETRY = "telemetry"
    TLE_HISTORY = "tle_history"
    OPERATOR_NOTES = "operator_notes"
    MAINTENANCE_RECORDS = "maintenance_records"
    PRIOR_ANALYSIS = "prior_analysis"
    SPACE_WEATHER = "space_weather"
    DEBRIS_ENVIRONMENT = "debris_environment"


class EvidenceItem(BaseModel):
    """A single piece of evidence from any source."""
    id: str = ""
    source: EvidenceSource
    data_type: str = ""           # e.g., "image/jpeg", "application/json", "text/plain"
    timestamp: str = ""           # ISO 8601 when the evidence was captured
    description: str = ""
    confidence: float = 1.0       # 0.0-1.0 — how reliable is this source
    payload: dict = {}            # Source-specific data
    metadata: dict = {}           # Additional context (sensor, provider, etc.)


class EvidenceBundle(BaseModel):
    """
    Unified evidence package for a satellite.

    Combines all available evidence sources into a single bundle
    that agents can consume for richer, more accurate analysis.
    """
    satellite_id: str = ""        # NORAD ID or internal ID
    satellite_name: str = ""
    items: list[EvidenceItem] = []

    # Summary statistics
    total_items: int = 0
    sources_available: list[str] = []
    earliest_evidence: str = ""   # ISO 8601
    latest_evidence: str = ""     # ISO 8601

    # Prior analysis context
    prior_analyses_count: int = 0
    prior_risk_tiers: list[str] = []  # Historical risk tier progression

    # Fusion metadata
    fused_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    fusion_confidence: float = 1.0  # Overall confidence in the fused bundle

    def add_item(self, item: EvidenceItem):
        self.items.append(item)
        self.total_items = len(self.items)
        if item.source.value not in self.sources_available:
            self.sources_available.append(item.source.value)

    def to_agent_context(self) -> str:
        """Convert bundle to text context for agent prompts."""
        parts = [f"Evidence Bundle for {self.satellite_name or self.satellite_id}:"]
        parts.append(f"  Sources: {', '.join(self.sources_available)}")
        parts.append(f"  Total evidence items: {self.total_items}")

        if self.prior_analyses_count > 0:
            parts.append(f"  Prior analyses: {self.prior_analyses_count}")
            parts.append(f"  Historical risk tiers: {' → '.join(self.prior_risk_tiers)}")

        for item in self.items:
            parts.append(f"\n  [{item.source.value}] {item.description}")
            if item.payload:
                for k, v in item.payload.items():
                    if isinstance(v, str) and len(v) > 200:
                        parts.append(f"    {k}: {v[:200]}...")
                    else:
                        parts.append(f"    {k}: {v}")

        return "\n".join(parts)
