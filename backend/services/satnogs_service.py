"""Public SatNOGS observation metadata lookup."""

from __future__ import annotations

from statistics import mean

import httpx

from config import settings


def normalize_observation(record: dict) -> dict:
    return {
        "id": record.get("id"),
        "norad_id": str(record.get("norad_cat_id") or ""),
        "start": record.get("start"),
        "end": record.get("end"),
        "station_name": record.get("station_name") or "",
        "vetted_status": record.get("vetted_status") or "",
        "max_altitude": record.get("max_altitude"),
        "archive_url": record.get("archive_url"),
        "transmitter_mode": record.get("transmitter_mode") or "",
        "transmitter_description": record.get("transmitter_description") or "",
        "transmitter_downlink_low": record.get("transmitter_downlink_low"),
    }


def summarize_observations(observations: list[dict]) -> dict:
    if not observations:
        return {
            "observation_count": 0,
            "latest_start": None,
            "distinct_stations": 0,
            "avg_max_altitude": None,
            "transmitter_modes": [],
        }
    max_altitudes = [obs["max_altitude"] for obs in observations if obs.get("max_altitude") is not None]
    return {
        "observation_count": len(observations),
        "latest_start": max((obs.get("start") or "" for obs in observations), default=None),
        "distinct_stations": len({obs.get("station_name") for obs in observations if obs.get("station_name")}),
        "avg_max_altitude": round(mean(max_altitudes), 2) if max_altitudes else None,
        "transmitter_modes": sorted({obs.get("transmitter_mode") for obs in observations if obs.get("transmitter_mode")}),
    }


async def fetch_recent_observations(norad_id: str, *, limit: int | None = None) -> list[dict]:
    count = limit or settings.SATNOGS_MAX_OBSERVATIONS
    base = settings.SATNOGS_NETWORK_API_BASE.rstrip("/")
    url = f"{base}/observations/"
    params = {
        "norad_cat_id": norad_id,
        "format": "json",
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(url, params=params)
        if response.status_code != 200:
            return []
        payload = response.json()
    observations = [normalize_observation(item) for item in payload[:count]]
    observations.sort(key=lambda item: item.get("start") or "", reverse=True)
    return observations[:count]
