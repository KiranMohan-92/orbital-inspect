"""Public UCS satellite database parser/lookup service."""

from __future__ import annotations

import csv
import io

import httpx

from config import settings


def _clean(value) -> str:
    return str(value or "").strip()


def _float(value):
    try:
        cleaned = _clean(value).replace(",", "")
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def parse_ucs_text(payload: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(payload), delimiter="	")
    return [row for row in reader if any(_clean(v) for v in row.values())]


def normalize_ucs_record(record: dict) -> dict:
    return {
        "norad_id": _clean(record.get("NORAD Number")),
        "satcat_id": _clean(record.get("NORAD Number")),
        "cospar_id": _clean(
            record.get("COSPAR Number")
            or record.get("COSPAR Number / International Designator")
            or record.get("International Designator")
        ),
        "name": _clean(record.get("Name of Satellite, Alternate Names")),
        "operator_name": _clean(record.get("Operator/Owner")),
        "country_of_operator": _clean(record.get("Country of Operator/Owner")),
        "users": _clean(record.get("Users")),
        "purpose": _clean(record.get("Purpose")),
        "orbit_class": _clean(record.get("Class of Orbit")),
        "orbit_type": _clean(record.get("Type of Orbit")),
        "longitude_geo_deg": _float(record.get("Longitude of GEO (degrees)")),
        "perigee_km": _float(record.get("Perigee (km)")),
        "apogee_km": _float(record.get("Apogee (km)")),
        "inclination_deg": _float(record.get("Inclination (degrees)")),
        "period_min": _float(record.get("Period (minutes)")),
        "launch_mass_kg": _float(record.get("Launch Mass (kg.)")),
        "dry_mass_kg": _float(record.get("Dry Mass (kg.)")),
        "power_w": _float(record.get("Power (watts)")),
        "expected_lifetime_yrs": _float(record.get("Expected Lifetime (yrs.)")),
        "manufacturer": _clean(record.get("Contractor")),
        "manufacturer_designation": _clean(
            record.get("Bus")
            or record.get("Series")
            or record.get("Platform")
        ),
        "launch_site": _clean(record.get("Launch Site")),
        "launch_vehicle": _clean(record.get("Launch Vehicle")),
    }


async def lookup_by_norad_id(norad_id: str, *, source_url: str | None = None) -> dict | None:
    url = source_url or settings.UCS_DATABASE_TEXT_URL
    if not url:
        return None
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        response = await client.get(url)
        if response.status_code != 200:
            return None
        records = parse_ucs_text(response.text)
    for record in records:
        if _clean(record.get("NORAD Number")) == str(norad_id):
            return normalize_ucs_record(record)
    return None
