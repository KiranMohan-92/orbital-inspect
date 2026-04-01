"""
Enhanced NOAA SWPC service for satellite weather intelligence.

Builds on the baseline space weather snapshot with interplanetary magnetic
field Bz, active alerts, and short/long-range forecast products.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from services.space_weather_service import SpaceWeatherSnapshot, fetch_space_weather

log = logging.getLogger(__name__)

SWPC_BASE = "https://services.swpc.noaa.gov"
_TIMEOUT = httpx.Timeout(10.0, read=15.0)


@dataclass
class EnhancedSpaceWeather(SpaceWeatherSnapshot):
    """Current and forecast space weather relevant to spacecraft health."""

    bz_nt: float = 0.0
    bt_nt: float = 0.0
    bz_orientation: str = "NEUTRAL"
    geoeffective: bool = False
    active_alerts: list[dict[str, Any]] = field(default_factory=list)
    highest_alert_level: str = "NONE"
    three_day_forecast: list[dict[str, Any]] = field(default_factory=list)
    twenty_seven_day_outlook: list[dict[str, Any]] = field(default_factory=list)


async def fetch_enhanced_space_weather() -> EnhancedSpaceWeather:
    """
    Fetch an enhanced space weather snapshot from NOAA SWPC.

    Each extra endpoint is optional; failures are logged and do not prevent
    the caller from receiving the baseline weather snapshot.
    """
    base = await fetch_space_weather()
    snapshot = EnhancedSpaceWeather(
        kp_index=base.kp_index,
        kp_category=base.kp_category,
        solar_wind_speed_km_s=base.solar_wind_speed_km_s,
        solar_wind_density_p_cm3=base.solar_wind_density_p_cm3,
        proton_flux_pfu=base.proton_flux_pfu,
        electron_flux=base.electron_flux,
        xray_flux=base.xray_flux,
        flare_class=base.flare_class,
        storm_warning=base.storm_warning,
        data_sources=list(base.data_sources or []),
    )

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            mag_payload = await _fetch_json(
                client,
                f"{SWPC_BASE}/products/solar-wind/mag-7-day.json",
            )
            bz_nt, bt_nt = await _extract_latest_bz(mag_payload)
            snapshot.bz_nt = bz_nt
            snapshot.bt_nt = bt_nt
            snapshot.bz_orientation = await _classify_bz_orientation(bz_nt)
            snapshot.geoeffective = bz_nt <= -5.0
            snapshot.data_sources.append("DSCOVR Solar Wind Magnetometer")
        except Exception:
            log.warning("Bz magnetometer fetch failed", exc_info=True)

        try:
            alerts_payload = await _fetch_json(client, f"{SWPC_BASE}/products/alerts.json")
            snapshot.active_alerts = await _normalize_alerts(alerts_payload)
            snapshot.highest_alert_level = await _highest_alert_level(snapshot.active_alerts)
            snapshot.data_sources.append("NOAA SWPC Alerts")
        except Exception:
            log.warning("Alerts fetch failed", exc_info=True)

        try:
            forecast_payload = await _fetch_forecast_payload(
                client,
                [
                    f"{SWPC_BASE}/products/forecasts/3-day-outlook.json",
                    f"{SWPC_BASE}/products/noaa-planetary-k-index-forecast.json",
                ],
            )
            snapshot.three_day_forecast = await _normalize_forecast_payload(forecast_payload)
            if snapshot.three_day_forecast:
                snapshot.data_sources.append("NOAA SWPC 3-Day Outlook")
        except Exception:
            log.warning("3-day forecast fetch failed", exc_info=True)

        try:
            outlook_payload = await _fetch_forecast_payload(
                client,
                [
                    f"{SWPC_BASE}/products/forecasts/27-day-outlook.json",
                    f"{SWPC_BASE}/products/27-day-outlook.json",
                ],
            )
            snapshot.twenty_seven_day_outlook = await _normalize_forecast_payload(outlook_payload)
            if snapshot.twenty_seven_day_outlook:
                snapshot.data_sources.append("NOAA SWPC 27-Day Outlook")
        except Exception:
            log.warning("27-day outlook fetch failed", exc_info=True)

    snapshot.storm_warning = (
        snapshot.storm_warning
        or snapshot.geoeffective
        or snapshot.highest_alert_level in {"WARNING", "CRITICAL"}
    )
    return snapshot


async def _fetch_json(client: httpx.AsyncClient, url: str) -> Any:
    resp = await client.get(url)
    resp.raise_for_status()
    return resp.json()


async def _fetch_forecast_payload(client: httpx.AsyncClient, urls: list[str]) -> Any:
    for url in urls:
        try:
            payload = await _fetch_json(client, url)
            if payload:
                return payload
        except Exception:
            log.info("Forecast endpoint unavailable", extra={"url": url})
    return []


async def _extract_latest_bz(payload: Any) -> tuple[float, float]:
    records = await _normalize_tabular_payload(payload)
    if not records:
        return 0.0, 0.0

    for record in reversed(records):
        bz_value = await _coerce_float(
            await _pick_value(record, "bz_gsm", "bz", "bz_nt", "Bz", "BZ_GSM"),
        )
        bt_value = await _coerce_float(
            await _pick_value(record, "bt", "bt_nt", "Bt", "BT"),
        )
        if bz_value == 0.0 and bt_value == 0.0:
            continue
        return bz_value, bt_value

    return 0.0, 0.0


async def _normalize_alerts(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        return []

    normalized: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue

        message = str(item.get("message", ""))
        classification = await _classify_alert(message)
        normalized.append(
            {
                "product_id": item.get("product_id", ""),
                "issue_datetime": item.get("issue_datetime", ""),
                "level": classification["level"],
                "severity": classification["severity"],
                "headline": classification["headline"],
                "message": message,
            }
        )

    normalized.sort(key=lambda item: str(item.get("issue_datetime", "")), reverse=True)
    return normalized


async def _classify_alert(message: str) -> dict[str, str]:
    text = (message or "").upper()
    headline = message.splitlines()[4].strip() if len(message.splitlines()) >= 5 else ""

    level = "SUMMARY"
    if "WARNING:" in text or "EXTENDED WARNING:" in text:
        level = "WARNING"
    elif "WATCH:" in text or "CANCEL WATCH:" in text:
        level = "WATCH"
    elif "ALERT:" in text or "CONTINUED ALERT:" in text:
        level = "ALERT"

    severity = "LOW"
    if any(token in text for token in ("G4", "G5", "R4", "R5", "S4", "S5", "SEVERE", "EXTREME")):
        severity = "CRITICAL"
    elif any(token in text for token in ("G2", "G3", "R2", "R3", "S2", "S3", "MODERATE", "STRONG")):
        severity = "HIGH"
    elif level in {"WARNING", "WATCH", "ALERT"}:
        severity = "MEDIUM"

    return {
        "level": level,
        "severity": severity,
        "headline": headline,
    }


async def _highest_alert_level(alerts: list[dict[str, Any]]) -> str:
    severity_order = {"NONE": 0, "SUMMARY": 1, "ALERT": 2, "WATCH": 3, "WARNING": 4, "CRITICAL": 5}
    highest = "NONE"
    highest_rank = -1

    for alert in alerts:
        level = str(alert.get("level", "NONE"))
        severity = str(alert.get("severity", "LOW"))
        rank = severity_order.get(level, 0)
        if severity == "CRITICAL":
            rank = severity_order["CRITICAL"]
        if rank > highest_rank:
            highest_rank = rank
            highest = "CRITICAL" if severity == "CRITICAL" else level

    return highest


async def _normalize_forecast_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        if isinstance(payload.get("periods"), list):
            return payload["periods"]
        return [payload]

    if isinstance(payload, list):
        if not payload:
            return []
        if all(isinstance(item, dict) for item in payload):
            return payload
        return await _normalize_tabular_payload(payload)

    return []


async def _normalize_tabular_payload(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list) or not payload:
        return []

    if all(isinstance(item, dict) for item in payload):
        return payload

    if not isinstance(payload[0], list):
        return []

    header = [str(value) for value in payload[0]]
    records: list[dict[str, Any]] = []
    for row in payload[1:]:
        if not isinstance(row, list):
            continue
        records.append(dict(zip(header, row)))
    return records


async def _classify_bz_orientation(bz_nt: float) -> str:
    if bz_nt <= -10:
        return "STRONGLY_SOUTHWARD"
    if bz_nt <= -5:
        return "SOUTHWARD"
    if bz_nt >= 5:
        return "NORTHWARD"
    return "NEUTRAL"


async def _pick_value(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in record and record[key] not in ("", None):
            return record[key]
    return None


async def _coerce_float(value: Any) -> float:
    if value in ("", None):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
