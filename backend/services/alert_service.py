"""Threshold-based alerting for fleet-scale satellite monitoring.

Evaluates asset health against configurable thresholds and dispatches
alert events via the webhook infrastructure.
"""

import logging
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class AlertThresholds:
    """Configurable thresholds for fleet monitoring alerts."""
    conjunction_miss_distance_km: float = 5.0  # Alert if conjunction < this distance
    risk_composite_critical: float = 80.0  # Alert if risk composite >= this
    risk_composite_high: float = 60.0  # Alert if risk composite >= this
    evidence_staleness_hours: float = 24.0  # Alert if evidence older than this
    triage_score_urgent: float = 80.0  # Alert if triage score >= this


@dataclass
class Alert:
    """A generated alert ready for dispatch."""
    alert_type: str  # alert.conjunction, alert.risk_threshold, alert.evidence_stale, alert.triage_urgent
    severity: str  # critical, high, medium, low
    asset_id: str | None
    asset_name: str | None
    norad_id: str | None
    analysis_id: str | None
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AlertService:
    """Evaluates metrics against thresholds and generates alerts."""

    def __init__(self, thresholds: AlertThresholds | None = None):
        self.thresholds = thresholds or AlertThresholds()
        self._recent_alerts: list[Alert] = []  # In-memory buffer for recent alerts

    def evaluate_risk_composite(
        self,
        *,
        asset_id: str | None,
        asset_name: str | None,
        norad_id: str | None,
        analysis_id: str | None,
        composite_score: float | None,
    ) -> Alert | None:
        """Check if risk composite exceeds threshold."""
        if composite_score is None:
            return None

        if composite_score >= self.thresholds.risk_composite_critical:
            severity = "critical"
            alert_type = "alert.risk_threshold"
        elif composite_score >= self.thresholds.risk_composite_high:
            severity = "high"
            alert_type = "alert.risk_threshold"
        else:
            return None

        alert = Alert(
            alert_type=alert_type,
            severity=severity,
            asset_id=asset_id,
            asset_name=asset_name,
            norad_id=norad_id,
            analysis_id=analysis_id,
            message=f"Risk composite {composite_score:.1f} exceeds {severity} threshold for {asset_name or norad_id or 'unknown asset'}",
            details={"composite_score": composite_score, "threshold": self.thresholds.risk_composite_critical if severity == "critical" else self.thresholds.risk_composite_high},
        )
        self._recent_alerts.append(alert)
        return alert

    def evaluate_conjunction_risk(
        self,
        *,
        asset_id: str | None,
        asset_name: str | None,
        norad_id: str | None,
        miss_distance_km: float | None,
        conjunction_object: str | None = None,
    ) -> Alert | None:
        """Check if conjunction miss distance is dangerously low."""
        if miss_distance_km is None:
            return None
        if miss_distance_km >= self.thresholds.conjunction_miss_distance_km:
            return None

        severity = "critical" if miss_distance_km < 1.0 else "high"
        alert = Alert(
            alert_type="alert.conjunction",
            severity=severity,
            asset_id=asset_id,
            asset_name=asset_name,
            norad_id=norad_id,
            analysis_id=None,
            message=f"Conjunction alert: {miss_distance_km:.2f} km miss distance for {asset_name or norad_id or 'unknown asset'}",
            details={
                "miss_distance_km": miss_distance_km,
                "threshold_km": self.thresholds.conjunction_miss_distance_km,
                "conjunction_object": conjunction_object,
            },
        )
        self._recent_alerts.append(alert)
        return alert

    def evaluate_evidence_freshness(
        self,
        *,
        asset_id: str | None,
        asset_name: str | None,
        norad_id: str | None,
        latest_evidence_at: datetime | None,
    ) -> Alert | None:
        """Check if evidence data is stale."""
        if latest_evidence_at is None:
            return None

        now = datetime.now(timezone.utc)
        # Make latest_evidence_at timezone-aware if needed
        if latest_evidence_at.tzinfo is None:
            latest_evidence_at = latest_evidence_at.replace(tzinfo=timezone.utc)

        age_hours = (now - latest_evidence_at).total_seconds() / 3600.0
        if age_hours < self.thresholds.evidence_staleness_hours:
            return None

        severity = "high" if age_hours > self.thresholds.evidence_staleness_hours * 3 else "medium"
        alert = Alert(
            alert_type="alert.evidence_stale",
            severity=severity,
            asset_id=asset_id,
            asset_name=asset_name,
            norad_id=norad_id,
            analysis_id=None,
            message=f"Evidence stale ({age_hours:.1f}h old) for {asset_name or norad_id or 'unknown asset'}",
            details={
                "age_hours": round(age_hours, 1),
                "threshold_hours": self.thresholds.evidence_staleness_hours,
                "latest_evidence_at": latest_evidence_at.isoformat(),
            },
        )
        self._recent_alerts.append(alert)
        return alert

    def evaluate_triage_score(
        self,
        *,
        asset_id: str | None,
        asset_name: str | None,
        norad_id: str | None,
        analysis_id: str | None,
        triage_score: float | None,
        triage_band: str | None,
    ) -> Alert | None:
        """Check if triage score indicates urgent attention needed."""
        if triage_score is None:
            return None
        if triage_score < self.thresholds.triage_score_urgent:
            return None

        alert = Alert(
            alert_type="alert.triage_urgent",
            severity="high",
            asset_id=asset_id,
            asset_name=asset_name,
            norad_id=norad_id,
            analysis_id=analysis_id,
            message=f"Urgent triage ({triage_band or 'unknown band'}, score {triage_score:.1f}) for {asset_name or norad_id or 'unknown asset'}",
            details={
                "triage_score": triage_score,
                "triage_band": triage_band,
                "threshold": self.thresholds.triage_score_urgent,
            },
        )
        self._recent_alerts.append(alert)
        return alert

    def get_recent_alerts(self, limit: int = 50) -> list[Alert]:
        """Return recent alerts from in-memory buffer."""
        return self._recent_alerts[-limit:]

    def to_webhook_payload(self, alert: Alert) -> dict[str, Any]:
        """Convert an alert to a webhook-compatible payload."""
        return {
            "event_type": alert.alert_type,
            "severity": alert.severity,
            "asset_id": alert.asset_id,
            "asset_name": alert.asset_name,
            "norad_id": alert.norad_id,
            "analysis_id": alert.analysis_id,
            "message": alert.message,
            "details": alert.details,
            "created_at": alert.created_at.isoformat(),
        }


# Module-level singleton
_instance: AlertService | None = None

def get_alert_service() -> AlertService:
    global _instance
    if _instance is None:
        _instance = AlertService()
    return _instance
