"""
Evidence fusion models for multi-source satellite intelligence.

Evidence sources include imagery, telemetry, orbital history,
public reference profiles, RF observations, operator maintenance
records, and prior analysis results.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

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


class EvidenceQualityStatus(str, Enum):
    """Decision quality state for an evidence item."""

    PRESENT = "present"
    MISSING = "missing"
    FETCH_FAILED = "fetch_failed"
    STALE = "stale"
    LOW_CONFIDENCE = "low_confidence"


class EvidenceItem(BaseModel):
    """A single piece of evidence from any source."""

    id: str = ""
    source: EvidenceSource
    data_type: str = ""
    timestamp: str = ""
    description: str = ""
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    quality_status: EvidenceQualityStatus = EvidenceQualityStatus.PRESENT
    required_for_decision: bool = False
    mission_relevance: Literal["critical", "supporting", "context"] = "supporting"
    captured_at: str = ""
    artifact_hash: str | None = None
    license: str | None = None
    payload: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)


class EvidenceBundle(BaseModel):
    """
    Unified evidence package for a satellite.

    Combines all available evidence sources into a single bundle
    that agents can consume for richer, more accurate analysis.
    """

    satellite_id: str = ""
    satellite_name: str = ""
    items: list[EvidenceItem] = Field(default_factory=list)

    total_items: int = 0
    sources_available: list[str] = Field(default_factory=list)
    earliest_evidence: str = ""
    latest_evidence: str = ""

    prior_analyses_count: int = 0
    prior_risk_tiers: list[str] = Field(default_factory=list)

    fused_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    fusion_confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    def add_item(self, item: EvidenceItem):
        self.items.append(item)
        self.total_items = len(self.items)
        if item.quality_status == EvidenceQualityStatus.PRESENT and item.source.value not in self.sources_available:
            self.sources_available.append(item.source.value)

    def add_quality_gap(
        self,
        *,
        source: EvidenceSource,
        status: EvidenceQualityStatus,
        description: str,
        error: str = "",
        required_for_decision: bool = True,
        mission_relevance: Literal["critical", "supporting", "context"] = "critical",
    ) -> None:
        self.add_item(
            EvidenceItem(
                source=source,
                data_type="quality_gap",
                description=description,
                confidence=0.0,
                quality_status=status,
                required_for_decision=required_for_decision,
                mission_relevance=mission_relevance,
                payload={"error": error} if error else {},
                metadata={"record_type": "negative_evidence"},
            )
        )

    def quality_summary(self, required_sources: set[str] | None = None) -> dict:
        required = required_sources or set()
        present_sources = {
            item.source.value
            for item in self.items
            if item.quality_status == EvidenceQualityStatus.PRESENT
        }
        explicit_gaps = [
            {
                "source": item.source.value,
                "status": item.quality_status.value,
                "description": item.description,
                "required_for_decision": item.required_for_decision,
                "mission_relevance": item.mission_relevance,
            }
            for item in self.items
            if item.quality_status != EvidenceQualityStatus.PRESENT
        ]
        missing_required = sorted(required - present_sources)
        for source in missing_required:
            if not any(gap["source"] == source for gap in explicit_gaps):
                explicit_gaps.append(
                    {
                        "source": source,
                        "status": EvidenceQualityStatus.MISSING.value,
                        "description": f"Required evidence source {source} was not available",
                        "required_for_decision": True,
                        "mission_relevance": "critical",
                    }
                )

        required_score = (
            len(present_sources & required) / len(required) * 100.0
            if required
            else 100.0
        )
        low_confidence_count = sum(
            1
            for item in self.items
            if item.quality_status == EvidenceQualityStatus.PRESENT and item.confidence < 0.7
        )
        failed_count = sum(
            1 for item in self.items if item.quality_status == EvidenceQualityStatus.FETCH_FAILED
        )
        stale_count = sum(
            1 for item in self.items if item.quality_status == EvidenceQualityStatus.STALE
        )
        penalty = min(40.0, low_confidence_count * 5.0 + failed_count * 10.0 + stale_count * 10.0)
        quality_score = max(0.0, round(required_score - penalty, 1))
        source_freshness = {
            item.source.value: item.captured_at or item.timestamp or item.metadata.get("captured_at") or ""
            for item in self.items
            if item.quality_status == EvidenceQualityStatus.PRESENT
        }
        return {
            "quality_score": quality_score,
            "required_sources": sorted(required),
            "present_required_sources": sorted(present_sources & required),
            "missing_required_sources": missing_required,
            "gaps": explicit_gaps,
            "failed_source_count": failed_count,
            "stale_source_count": stale_count,
            "low_confidence_count": low_confidence_count,
            "source_freshness": source_freshness,
        }

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
