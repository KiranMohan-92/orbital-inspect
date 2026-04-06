"""Optional Space-Track service for SATCAT enrichment."""

from __future__ import annotations

import logging

import httpx

from config import settings

log = logging.getLogger(__name__)


def space_track_configured() -> bool:
    return bool(settings.SPACE_TRACK_USERNAME and settings.SPACE_TRACK_PASSWORD)


def _normalize_satcat_record(record: dict) -> dict:
    return {
        "norad_id": str(record.get("NORAD_CAT_ID") or record.get("NORAD_CAT_ID", "")),
        "satcat_id": str(record.get("NORAD_CAT_ID") or record.get("NORAD_CAT_ID", "")),
        "cospar_id": record.get("OBJECT_ID") or record.get("INTLDES") or "",
        "name": record.get("OBJECT_NAME") or record.get("SATNAME") or "",
        "country_code": record.get("COUNTRY") or record.get("COUNTRY_CODE") or "",
        "launch_date": record.get("LAUNCH") or record.get("LAUNCH_DATE"),
        "launch_year": record.get("LAUNCH_YEAR"),
        "object_type": record.get("OBJECT_TYPE") or record.get("OBJECT_TYPE_DESC"),
        "site": record.get("SITE") or record.get("LAUNCH_SITE_DESC"),
        "status": record.get("OPS_STATUS_CODE") or record.get("OPS_STATUS"),
        "owner": record.get("OWNER") or record.get("OWNER_NAME"),
    }


async def lookup_satcat_by_norad_id(norad_id: str) -> dict | None:
    if not space_track_configured():
        return None

    base = settings.SPACE_TRACK_BASE_URL.rstrip("/")
    login_url = f"{base}/ajaxauth/login"
    query_url = (
        f"{base}/basicspacedata/query/class/satcat/"
        f"NORAD_CAT_ID/{norad_id}/format/json"
    )
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        login = await client.post(
            login_url,
            data={
                "identity": settings.SPACE_TRACK_USERNAME,
                "password": settings.SPACE_TRACK_PASSWORD,
            },
        )
        if login.status_code >= 400:
            log.warning("Space-Track login failed", extra={"status_code": login.status_code})
            return None
        response = await client.get(query_url)
        if response.status_code != 200:
            return None
        data = response.json()
        if not data:
            return None
        return _normalize_satcat_record(data[0])
