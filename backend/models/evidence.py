"""
Evidence fusion models for multi-source satellite intelligence.

Evidence sources include imagery, telemetry, orbital history,
public reference profiles, RF observations, operator maintenance
records, and prior analysis results.
"""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class EvidenceSource(str, Enum):
    """Types of evidence that can be fused into an analysis."""

    IMAGERY = "imagery"
    TELEMETRY = "telemetry"
    TLE_HISTORY = "tle_history"
    CONJUNCTION_RISK = "conjunction_risk"
    OPERATOR_NOTES = "operator_notes"
    MAINTENANCE_RECORDS = "maintenance_records"
    PRIOR_ANALYSIS = "prior_analysis"
    SPACE_WEATHER = "space_weather"
    DEBRIS_ENVIRONMENT = "debris_environment"
    REFERENCE_PROFILE = "reference_profile"
    RF_ACTIVITY = "rf_activity"


class EvidenceItem(BaseModel):
    """A single piece of evidence from any source."""

    id: str = ""
    source: EvidenceSource
    data_type: str = ""
    timestamp: str = ""
    description: str = ""
    confidence: float = 1.0
    payload: dict = {}
    metadata: dict = {}


class EvidenceBundle(BaseModel):
    """
    Unified evidence package for a satellite.

    Combines all available evidence sources into a single bundle
    that agents can consume for richer, more accurate analysis.
    """

    satellite_id: str = ""
    satellite_name: str = ""
    items: list[EvidenceItem] = []

    total_items: int = 0
    sources_available: list[str] = []
    earliest_evidence: str = ""
    latest_evidence: str = ""

    prior_analyses_count: int = 0
    prior_risk_tiers: list[str] = []

    fused_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    fusion_confidence: float = 1.0

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
                for key, value in item.payload.items():
                    if isinstance(value, str) and len(value) > 200:
                        parts.append(f"    {key}: {value[:200]}...")
                    else:
                        parts.append(f"    {key}: {value}")

        return "\n".join(parts)
