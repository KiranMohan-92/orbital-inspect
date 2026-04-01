"""
TLE history analysis service for orbital health intelligence.

Fetches recent CelesTrak GP history for a NORAD object and derives
orbital health indicators that are useful for underwriting and claims
investigation.
"""

from __future__ import annotations

import csv
import io
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from statistics import pstdev
from typing import Any

import httpx

log = logging.getLogger(__name__)

CELESTRAK_ELEMENTS_BASE = "https://celestrak.org/NORAD/elements"
EARTH_RADIUS_KM = 6378.137
EARTH_MU_KM3_S2 = 398600.4418
_TIMEOUT = httpx.Timeout(10.0, read=20.0)


@dataclass
class ManeuverEvent:
    """A likely propulsive or attitude-control event inferred from TLE jumps."""

    epoch: str = ""
    delta_altitude_km: float = 0.0
    delta_eccentricity: float = 0.0
    delta_inclination_deg: float = 0.0
    estimated_delta_v_m_s: float = 0.0
    severity: str = "LOW"


@dataclass
class TleHistoryAnalysis:
    """Derived orbital health metrics from recent TLE history."""

    norad_id: str = ""
    analysis_window_days: int = 90
    sample_count: int = 0
    history_start: str = ""
    history_end: str = ""
    altitude_stability_km: float = 0.0
    orbit_decay_rate_km_per_day: float = 0.0
    eccentricity_stability: float = 0.0
    inclination_drift_deg_per_day: float = 0.0
    maneuver_count: int = 0
    maneuver_frequency_90d: float = 0.0
    minimum_altitude_km: float = 0.0
    maximum_altitude_km: float = 0.0
    overall_health_score: int = 0
    health_rating: str = "UNKNOWN"
    detected_maneuvers: list[ManeuverEvent] = field(default_factory=list)
    data_sources: list[str] = field(default_factory=lambda: ["CelesTrak GP"])


@dataclass
class _HistoryPoint:
    epoch: datetime
    epoch_text: str
    mean_motion_rev_day: float
    semi_major_axis_km: float
    altitude_avg_km: float
    eccentricity: float
    inclination_deg: float


async def fetch_tle_history(norad_id: str, days: int = 90) -> list[dict[str, Any]]:
    """
    Fetch recent TLE/OMM history for a NORAD ID from CelesTrak.

    CelesTrak has evolved its history endpoints over time, so this function
    tries a small set of date-range query variants and accepts either JSON or
    CSV responses. Failures are logged and result in an empty history.
    """
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=days)

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        for candidate in await _build_history_candidates(norad_id, start_time, end_time):
            try:
                resp = await client.get(candidate["url"], params=candidate["params"])
                if resp.status_code != 200:
                    continue

                records = await _parse_history_response(resp)
                if not records:
                    continue

                filtered = await _filter_history_window(records, start_time, end_time)
                if filtered:
                    log.info(
                        "Fetched TLE history",
                        extra={
                            "norad_id": norad_id,
                            "records": len(filtered),
                            "endpoint": candidate["url"],
                        },
                    )
                    return filtered
            except Exception:
                log.warning(
                    "TLE history fetch failed",
                    exc_info=True,
                    extra={"norad_id": norad_id, "endpoint": candidate["url"]},
                )

    return []


async def analyze_tle_history(norad_id: str, days: int = 90) -> TleHistoryAnalysis:
    """Fetch and analyze recent TLE history for a NORAD object."""
    records = await fetch_tle_history(norad_id, days=days)
    return await analyze_tle_records(norad_id, records, days=days)


async def analyze_tle_records(
    norad_id: str,
    records: list[dict[str, Any]],
    days: int = 90,
) -> TleHistoryAnalysis:
    """Analyze a supplied set of TLE/OMM records."""
    points: list[_HistoryPoint] = []
    for record in records:
        point = await _record_to_point(record)
        if point is not None:
            points.append(point)

    points.sort(key=lambda point: point.epoch)

    analysis = TleHistoryAnalysis(
        norad_id=norad_id,
        analysis_window_days=days,
        sample_count=len(points),
    )

    if not points:
        return analysis

    altitudes = [point.altitude_avg_km for point in points]
    semi_major_axes = [point.semi_major_axis_km for point in points]
    eccentricities = [point.eccentricity for point in points]
    inclinations = [point.inclination_deg for point in points]
    offsets_days = await _offsets_in_days(points)

    maneuvers = await _detect_maneuvers(points)
    observed_span_days = max(
        1.0,
        (points[-1].epoch - points[0].epoch).total_seconds() / 86400.0,
    )

    analysis.history_start = points[0].epoch_text
    analysis.history_end = points[-1].epoch_text
    analysis.altitude_stability_km = round(pstdev(semi_major_axes), 3)
    analysis.orbit_decay_rate_km_per_day = round(
        await _linear_regression_slope(offsets_days, altitudes),
        4,
    )
    analysis.eccentricity_stability = round(pstdev(eccentricities), 6)
    analysis.inclination_drift_deg_per_day = round(
        await _linear_regression_slope(offsets_days, inclinations),
        5,
    )
    analysis.maneuver_count = len(maneuvers)
    analysis.maneuver_frequency_90d = round(len(maneuvers) * days / observed_span_days, 2)
    analysis.minimum_altitude_km = round(min(altitudes), 3)
    analysis.maximum_altitude_km = round(max(altitudes), 3)
    analysis.detected_maneuvers = maneuvers
    analysis.overall_health_score = await _score_orbital_health(analysis)
    analysis.health_rating = await _health_rating(analysis.overall_health_score)
    return analysis


async def _build_history_candidates(
    norad_id: str,
    start_time: datetime,
    end_time: datetime,
) -> list[dict[str, Any]]:
    start_date = start_time.strftime("%Y-%m-%d")
    end_date = end_time.strftime("%Y-%m-%d")
    return [
        {
            "url": f"{CELESTRAK_ELEMENTS_BASE}/gp-history.php",
            "params": {
                "CATNR": norad_id,
                "START": start_date,
                "STOP": end_date,
                "FORMAT": "json",
            },
        },
        {
            "url": f"{CELESTRAK_ELEMENTS_BASE}/gp-history.php",
            "params": {
                "CATNR": norad_id,
                "EPOCH": f"{start_date}--{end_date}",
                "FORMAT": "json",
            },
        },
        {
            "url": f"{CELESTRAK_ELEMENTS_BASE}/gp.php",
            "params": {
                "CATNR": norad_id,
                "START": start_date,
                "STOP": end_date,
                "FORMAT": "json",
            },
        },
        {
            "url": f"{CELESTRAK_ELEMENTS_BASE}/gp.php",
            "params": {
                "CATNR": norad_id,
                "EPOCH": f"{start_date}--{end_date}",
                "FORMAT": "json",
            },
        },
    ]


async def _parse_history_response(resp: httpx.Response) -> list[dict[str, Any]]:
    content_type = resp.headers.get("content-type", "").lower()

    if "json" in content_type:
        payload = resp.json()
        return await _normalize_history_payload(payload)

    text = resp.text.strip()
    if not text:
        return []

    if text[0] in "[{":
        try:
            return await _normalize_history_payload(resp.json())
        except ValueError:
            pass

    return await _parse_history_csv(text)


async def _normalize_history_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        return [payload]

    if isinstance(payload, list):
        if not payload:
            return []
        if all(isinstance(item, dict) for item in payload):
            return payload
        if isinstance(payload[0], list):
            header = [str(value) for value in payload[0]]
            normalized: list[dict[str, Any]] = []
            for row in payload[1:]:
                normalized.append(dict(zip(header, row)))
            return normalized

    return []


async def _parse_history_csv(text: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


async def _filter_history_window(
    records: list[dict[str, Any]],
    start_time: datetime,
    end_time: datetime,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    seen_epochs: set[str] = set()

    for record in records:
        epoch_text = await _extract_value(record, "EPOCH", "epoch")
        epoch = await _parse_datetime(epoch_text)
        if epoch is None or epoch < start_time or epoch > end_time:
            continue
        if epoch_text in seen_epochs:
            continue
        filtered.append(record)
        seen_epochs.add(epoch_text)

    filtered.sort(key=lambda record: str(record.get("EPOCH") or record.get("epoch") or ""))
    return filtered


async def _record_to_point(record: dict[str, Any]) -> _HistoryPoint | None:
    epoch_text = str(await _extract_value(record, "EPOCH", "epoch") or "")
    epoch = await _parse_datetime(epoch_text)
    if epoch is None:
        return None

    mean_motion = await _as_float(
        await _extract_value(record, "MEAN_MOTION", "mean_motion"),
    )
    if mean_motion <= 0:
        return None

    eccentricity = await _as_float(
        await _extract_value(record, "ECCENTRICITY", "eccentricity"),
    )
    inclination = await _as_float(
        await _extract_value(record, "INCLINATION", "inclination", "inclination_deg"),
    )

    semi_major_axis = await _semi_major_axis_from_mean_motion(mean_motion)
    altitude_avg = semi_major_axis - EARTH_RADIUS_KM

    apoapsis = await _as_float(
        await _extract_value(record, "APOAPSIS", "apoapsis_km", "apoapsis"),
    )
    periapsis = await _as_float(
        await _extract_value(record, "PERIAPSIS", "periapsis_km", "periapsis"),
    )
    if apoapsis > 0 and periapsis > 0:
        altitude_avg = (apoapsis + periapsis) / 2.0

    return _HistoryPoint(
        epoch=epoch,
        epoch_text=epoch.isoformat(),
        mean_motion_rev_day=mean_motion,
        semi_major_axis_km=semi_major_axis,
        altitude_avg_km=altitude_avg,
        eccentricity=eccentricity,
        inclination_deg=inclination,
    )


async def _offsets_in_days(points: list[_HistoryPoint]) -> list[float]:
    first_epoch = points[0].epoch
    return [
        (point.epoch - first_epoch).total_seconds() / 86400.0
        for point in points
    ]


async def _detect_maneuvers(points: list[_HistoryPoint]) -> list[ManeuverEvent]:
    if len(points) < 2:
        return []

    altitude_jumps = [
        abs(curr.altitude_avg_km - prev.altitude_avg_km)
        for prev, curr in zip(points, points[1:])
    ]
    eccentricity_jumps = [
        abs(curr.eccentricity - prev.eccentricity)
        for prev, curr in zip(points, points[1:])
    ]
    inclination_jumps = [
        abs(curr.inclination_deg - prev.inclination_deg)
        for prev, curr in zip(points, points[1:])
    ]

    altitude_threshold = min(
        max(5.0, pstdev(altitude_jumps) * 3.0 if len(altitude_jumps) > 1 else 0.0),
        8.0,
    )
    eccentricity_threshold = min(
        max(
            0.0005,
            pstdev(eccentricity_jumps) * 3.0 if len(eccentricity_jumps) > 1 else 0.0,
        ),
        0.001,
    )
    inclination_threshold = min(
        max(
            0.03,
            pstdev(inclination_jumps) * 3.0 if len(inclination_jumps) > 1 else 0.0,
        ),
        0.05,
    )

    events: list[ManeuverEvent] = []
    for prev, curr in zip(points, points[1:]):
        delta_altitude = curr.altitude_avg_km - prev.altitude_avg_km
        delta_eccentricity = curr.eccentricity - prev.eccentricity
        delta_inclination = curr.inclination_deg - prev.inclination_deg

        if (
            abs(delta_altitude) < altitude_threshold
            and abs(delta_eccentricity) < eccentricity_threshold
            and abs(delta_inclination) < inclination_threshold
        ):
            continue

        delta_v = await _estimate_delta_v(prev.semi_major_axis_km, curr.semi_major_axis_km)
        severity = "LOW"
        if abs(delta_altitude) >= 20 or delta_v >= 8:
            severity = "HIGH"
        elif abs(delta_altitude) >= 8 or delta_v >= 3:
            severity = "MEDIUM"

        events.append(
            ManeuverEvent(
                epoch=curr.epoch_text,
                delta_altitude_km=round(delta_altitude, 3),
                delta_eccentricity=round(delta_eccentricity, 6),
                delta_inclination_deg=round(delta_inclination, 5),
                estimated_delta_v_m_s=round(delta_v, 3),
                severity=severity,
            )
        )

    return events


async def _score_orbital_health(analysis: TleHistoryAnalysis) -> int:
    stability_score = max(0.0, 100.0 - min(100.0, analysis.altitude_stability_km / 40.0 * 100.0))

    if analysis.orbit_decay_rate_km_per_day >= 0:
        decay_score = 100.0
    else:
        decay_score = max(
            0.0,
            100.0 - min(100.0, abs(analysis.orbit_decay_rate_km_per_day) / 0.25 * 100.0),
        )

    eccentricity_score = max(
        0.0,
        100.0 - min(100.0, analysis.eccentricity_stability / 0.002 * 100.0),
    )
    inclination_score = max(
        0.0,
        100.0 - min(100.0, abs(analysis.inclination_drift_deg_per_day) / 0.05 * 100.0),
    )
    maneuver_score = max(
        0.0,
        100.0 - min(100.0, analysis.maneuver_frequency_90d / 8.0 * 100.0),
    )

    weighted = (
        stability_score * 0.30
        + decay_score * 0.25
        + eccentricity_score * 0.20
        + inclination_score * 0.15
        + maneuver_score * 0.10
    )
    return max(0, min(100, round(weighted)))


async def _health_rating(score: int) -> str:
    if score >= 85:
        return "EXCELLENT"
    if score >= 70:
        return "GOOD"
    if score >= 50:
        return "WATCH"
    return "POOR"


async def _linear_regression_slope(x_values: list[float], y_values: list[float]) -> float:
    if len(x_values) < 2 or len(y_values) < 2 or len(x_values) != len(y_values):
        return 0.0

    mean_x = sum(x_values) / len(x_values)
    mean_y = sum(y_values) / len(y_values)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_values, y_values))
    denominator = sum((x - mean_x) ** 2 for x in x_values)
    if denominator == 0:
        return 0.0
    return numerator / denominator


async def _semi_major_axis_from_mean_motion(mean_motion_rev_day: float) -> float:
    mean_motion_rad_s = mean_motion_rev_day * 2.0 * math.pi / 86400.0
    return (EARTH_MU_KM3_S2 / (mean_motion_rad_s ** 2)) ** (1.0 / 3.0)


async def _estimate_delta_v(semi_major_axis_1_km: float, semi_major_axis_2_km: float) -> float:
    average_axis = (semi_major_axis_1_km + semi_major_axis_2_km) / 2.0
    if average_axis <= 0:
        return 0.0

    orbital_speed_km_s = math.sqrt(EARTH_MU_KM3_S2 / average_axis)
    delta_axis = abs(semi_major_axis_2_km - semi_major_axis_1_km)
    return 0.5 * orbital_speed_km_s * delta_axis / average_axis * 1000.0


async def _extract_value(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in record and record[key] not in ("", None):
            return record[key]
    return None


async def _as_float(value: Any) -> float:
    if value in ("", None):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


async def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None

    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        else:
            return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
