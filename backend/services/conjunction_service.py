"""
Conjunction risk service using CelesTrak SOCRATES data.

Provides close-approach history and a simple insurer-facing conjunction risk
score based on encounter frequency and minimum miss distance.
"""

from __future__ import annotations

import csv
import io
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

log = logging.getLogger(__name__)

SOCRATES_BASE_URLS = [
    "https://celestrak.org/SOCRATES/table-socrates.php",
    "https://celestrak.org/socrates/table-socrates.php",
]
_TIMEOUT = httpx.Timeout(10.0, read=20.0)


@dataclass
class ConjunctionEvent:
    """A single close-approach event from SOCRATES data."""

    tca: str = ""
    miss_distance_km: float = 0.0
    relative_speed_km_s: float = 0.0
    collision_probability: float = 0.0
    counterparty_norad_id: str = ""
    counterparty_name: str = ""
    is_debris: bool = False
    severity: str = "LOW"


@dataclass
class ConjunctionRiskAssessment:
    """Summarized conjunction environment for one spacecraft."""

    norad_id: str = ""
    event_count: int = 0
    minimum_miss_distance_km: float = 0.0
    average_miss_distance_km: float = 0.0
    conjunction_risk_score: int = 0
    miss_distance_history_km: list[float] = field(default_factory=list)
    most_threatening_objects: list[dict[str, Any]] = field(default_factory=list)
    events: list[ConjunctionEvent] = field(default_factory=list)
    data_source: str = "CelesTrak SOCRATES"


async def fetch_conjunction_events(norad_id: str, max_events: int = 50) -> list[ConjunctionEvent]:
    """
    Fetch recent close approaches for a satellite from CelesTrak SOCRATES.

    The endpoint format can vary between HTML and CSV-like outputs, so this
    function attempts a small number of URL variants and parsers.
    """
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        for url in SOCRATES_BASE_URLS:
            try:
                resp = await client.get(
                    url,
                    params={
                        "CATNR": f"{norad_id},",
                        "ORDER": "MINRANGE",
                        "MAX": str(max_events),
                        "FORMAT": "CSV",
                    },
                )
                if resp.status_code != 200:
                    continue

                events = await _parse_socrates_payload(resp.text, norad_id)
                if events:
                    log.info(
                        "Fetched conjunction events",
                        extra={"norad_id": norad_id, "events": len(events), "url": url},
                    )
                    return events[:max_events]
            except Exception:
                log.warning(
                    "Conjunction fetch failed",
                    exc_info=True,
                    extra={"norad_id": norad_id, "url": url},
                )

    return []


async def assess_conjunction_risk(
    norad_id: str,
    max_events: int = 50,
) -> ConjunctionRiskAssessment:
    """Fetch conjunction data and compute a risk assessment."""
    events = await fetch_conjunction_events(norad_id, max_events=max_events)
    return await calculate_conjunction_risk(norad_id, events)


async def calculate_conjunction_risk(
    norad_id: str,
    events: list[ConjunctionEvent],
) -> ConjunctionRiskAssessment:
    """Compute conjunction risk metrics from supplied close-approach events."""
    assessment = ConjunctionRiskAssessment(norad_id=norad_id, events=events)
    if not events:
        return assessment

    miss_distances = [event.miss_distance_km for event in events if event.miss_distance_km > 0]
    if miss_distances:
        assessment.minimum_miss_distance_km = round(min(miss_distances), 3)
        assessment.average_miss_distance_km = round(sum(miss_distances) / len(miss_distances), 3)
        assessment.miss_distance_history_km = [round(distance, 3) for distance in miss_distances]

    assessment.event_count = len(events)
    assessment.most_threatening_objects = await _summarize_threats(events)
    assessment.conjunction_risk_score = await _score_conjunction_risk(events)
    return assessment


async def _parse_socrates_payload(text: str, norad_id: str) -> list[ConjunctionEvent]:
    stripped = text.strip()
    if not stripped:
        return []

    if "," in stripped and "<table" not in stripped.lower():
        return await _parse_socrates_csv(stripped, norad_id)

    return await _parse_socrates_html(stripped, norad_id)


async def _parse_socrates_csv(text: str, norad_id: str) -> list[ConjunctionEvent]:
    reader = csv.DictReader(io.StringIO(text))
    events: list[ConjunctionEvent] = []
    for row in reader:
        event = await _row_to_conjunction_event(row, norad_id)
        if event is not None:
            events.append(event)
    return events


async def _parse_socrates_html(text: str, norad_id: str) -> list[ConjunctionEvent]:
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", text, flags=re.IGNORECASE | re.DOTALL)
    if len(rows) < 2:
        return []

    headers = [
        await _clean_html(cell)
        for cell in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", rows[0], flags=re.IGNORECASE | re.DOTALL)
    ]
    if not headers:
        return []

    events: list[ConjunctionEvent] = []
    for row in rows[1:]:
        cells = [
            await _clean_html(cell)
            for cell in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, flags=re.IGNORECASE | re.DOTALL)
        ]
        if not cells:
            continue
        record = dict(zip(headers, cells))
        event = await _row_to_conjunction_event(record, norad_id)
        if event is not None:
            events.append(event)
    return events


async def _row_to_conjunction_event(
    row: dict[str, Any],
    norad_id: str,
) -> ConjunctionEvent | None:
    tca = str(
        await _pick_value(
            row,
            "TCA",
            "Time of Closest Approach",
            "TIME_OF_CLOSEST_APPROACH",
        )
        or ""
    )
    miss_distance = await _coerce_float(
        await _pick_value(
            row,
            "MIN_RNG",
            "MIN_RANGE",
            "Minimum Range",
            "MISS_DISTANCE_KM",
        )
    )
    if miss_distance <= 0:
        return None

    collision_probability = await _coerce_float(
        await _pick_value(row, "MAX_PROB", "Probability", "COLLISION_PROBABILITY", "PC")
    )
    relative_speed = await _coerce_float(
        await _pick_value(row, "REL_SPEED", "Relative Speed", "RELATIVE_SPEED")
    )

    object_1_id = str(await _pick_value(row, "CATNR1", "SCC_NUM_1", "NORAD_CAT_ID_1") or "")
    object_2_id = str(await _pick_value(row, "CATNR2", "SCC_NUM_2", "NORAD_CAT_ID_2") or "")
    object_1_name = str(await _pick_value(row, "NAME1", "OBJECT_NAME_1", "OBJECT1") or "")
    object_2_name = str(await _pick_value(row, "NAME2", "OBJECT_NAME_2", "OBJECT2") or "")

    counterparty_norad = object_2_id if object_1_id == norad_id else object_1_id
    counterparty_name = object_2_name if object_1_id == norad_id else object_1_name
    if not counterparty_norad and object_2_id:
        counterparty_norad = object_2_id
        counterparty_name = object_2_name

    is_debris = "DEB" in counterparty_name.upper() or " R/B" in counterparty_name.upper()

    severity = "LOW"
    if miss_distance <= 1.0 or collision_probability >= 1e-4:
        severity = "HIGH"
    elif miss_distance <= 5.0 or collision_probability >= 1e-5:
        severity = "MEDIUM"

    return ConjunctionEvent(
        tca=tca,
        miss_distance_km=miss_distance,
        relative_speed_km_s=relative_speed,
        collision_probability=collision_probability,
        counterparty_norad_id=counterparty_norad,
        counterparty_name=counterparty_name,
        is_debris=is_debris,
        severity=severity,
    )


async def _summarize_threats(events: list[ConjunctionEvent]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for event in events:
        key = event.counterparty_norad_id or event.counterparty_name or "unknown"
        if key not in grouped:
            grouped[key] = {
                "counterparty_norad_id": event.counterparty_norad_id,
                "counterparty_name": event.counterparty_name,
                "is_debris": event.is_debris,
                "closest_miss_distance_km": event.miss_distance_km,
                "event_count": 1,
            }
            continue

        grouped[key]["event_count"] += 1
        grouped[key]["closest_miss_distance_km"] = min(
            grouped[key]["closest_miss_distance_km"],
            event.miss_distance_km,
        )

    ranked = sorted(
        grouped.values(),
        key=lambda item: (item["closest_miss_distance_km"], -item["event_count"]),
    )
    return ranked[:5]


async def _score_conjunction_risk(events: list[ConjunctionEvent]) -> int:
    if not events:
        return 0

    event_count = len(events)
    min_distance = min(event.miss_distance_km for event in events)
    max_probability = max(event.collision_probability for event in events)
    debris_events = sum(1 for event in events if event.is_debris)

    frequency_component = min(35.0, event_count * 6.0)
    if min_distance <= 1.0:
        distance_component = 40.0
    elif min_distance <= 5.0:
        distance_component = 30.0
    elif min_distance <= 10.0:
        distance_component = 20.0
    elif min_distance <= 25.0:
        distance_component = 10.0
    else:
        distance_component = 5.0

    probability_component = min(15.0, max_probability * 1e6)
    debris_component = min(10.0, debris_events * 2.0)

    score = frequency_component + distance_component + probability_component + debris_component
    return max(0, min(100, round(score)))


async def _pick_value(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row[key] not in ("", None):
            return row[key]
    return None


async def _coerce_float(value: Any) -> float:
    if value in ("", None):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


async def _clean_html(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", value)
    cleaned = re.sub(r"\s+", " ", without_tags)
    return cleaned.strip()
