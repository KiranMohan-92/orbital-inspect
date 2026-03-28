"""
CelesTrak API service for satellite catalog lookup.

Provides satellite identification and orbital parameters from
the free CelesTrak GP (General Perturbations) data API.

API docs: https://celestrak.org/NORAD/documentation/gp-data-formats.php
"""

import httpx
from typing import Optional

CELESTRAK_BASE = "https://celestrak.org/NORAD/elements/gp.php"

# Common satellite groups for browsing
SATELLITE_GROUPS = {
    "stations": "Space Stations (ISS, Tiangong)",
    "active": "All Active Satellites",
    "starlink": "SpaceX Starlink",
    "oneweb": "OneWeb",
    "geo": "Geostationary",
    "weather": "Weather Satellites",
    "science": "Science Satellites",
    "gps-ops": "GPS Operational",
    "galileo": "Galileo Navigation",
    "iridium-NEXT": "Iridium NEXT",
    "intelsat": "Intelsat",
    "ses": "SES",
}


async def lookup_by_norad_id(norad_id: str) -> dict | None:
    """
    Look up a satellite by NORAD catalog number.
    Returns orbital elements and metadata.
    """
    params = {
        "CATNR": norad_id,
        "FORMAT": "json",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(CELESTRAK_BASE, params=params)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if not data:
            return None
        return _normalize_gp_record(data[0])


async def lookup_by_name(name: str) -> list[dict]:
    """
    Search satellites by name (partial match).
    Returns list of matching satellites.
    """
    params = {
        "NAME": name,
        "FORMAT": "json",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(CELESTRAK_BASE, params=params)
        if resp.status_code != 200:
            return []
        data = resp.json()
        return [_normalize_gp_record(r) for r in data[:20]]


async def list_group(group: str, limit: int = 50) -> list[dict]:
    """
    List satellites in a predefined group.
    """
    params = {
        "GROUP": group,
        "FORMAT": "json",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(CELESTRAK_BASE, params=params)
        if resp.status_code != 200:
            return []
        data = resp.json()
        return [_normalize_gp_record(r) for r in data[:limit]]


def classify_orbital_regime(
    period_min: float | None,
    apoapsis_km: float | None,
    periapsis_km: float | None,
    inclination_deg: float | None,
) -> str:
    """Classify orbital regime from orbital elements."""
    if apoapsis_km is None or periapsis_km is None:
        return "UNKNOWN"

    avg_alt = (apoapsis_km + periapsis_km) / 2

    # GEO: ~35,786 km altitude, near-zero inclination
    if 35000 < avg_alt < 36500:
        return "GEO"

    # HEO: highly elliptical (large difference between apo/peri)
    if apoapsis_km > 35000 and periapsis_km < 2000:
        return "HEO"

    # MEO: 2,000-35,000 km
    if 2000 < avg_alt < 35000:
        return "MEO"

    # SSO: LEO with specific inclination (~97-99°)
    if avg_alt < 2000 and inclination_deg and 96 < inclination_deg < 100:
        return "SSO"

    # LEO: below 2,000 km
    if avg_alt < 2000:
        return "LEO"

    return "UNKNOWN"


def _normalize_gp_record(record: dict) -> dict:
    """Normalize a CelesTrak GP record to a consistent format."""
    apoapsis = record.get("APOAPSIS")
    periapsis = record.get("PERIAPSIS")
    inclination = record.get("INCLINATION")
    period = record.get("PERIOD")

    return {
        "norad_id": str(record.get("NORAD_CAT_ID", "")),
        "name": record.get("OBJECT_NAME", ""),
        "cospar_id": record.get("OBJECT_ID", ""),
        "epoch": record.get("EPOCH", ""),
        "mean_motion": record.get("MEAN_MOTION"),
        "eccentricity": record.get("ECCENTRICITY"),
        "inclination_deg": inclination,
        "raan_deg": record.get("RA_OF_ASC_NODE"),
        "arg_pericenter_deg": record.get("ARG_OF_PERICENTER"),
        "mean_anomaly_deg": record.get("MEAN_ANOMALY"),
        "period_min": period,
        "apoapsis_km": apoapsis,
        "periapsis_km": periapsis,
        "rcs_size": record.get("RCS_SIZE", ""),  # SMALL, MEDIUM, LARGE
        "country_code": record.get("COUNTRY_CODE", ""),
        "launch_date": record.get("LAUNCH_DATE", ""),
        "decay_date": record.get("DECAY_DATE"),
        "orbital_regime": classify_orbital_regime(period, apoapsis, periapsis, inclination),
        "altitude_avg_km": round((apoapsis + periapsis) / 2, 1) if apoapsis and periapsis else None,
    }
