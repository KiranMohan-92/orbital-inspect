"""Fleet ingestion service — continuous background monitoring of registered assets.

Pulls latest orbital data, conjunction risk, and space weather for all
registered fleet assets and persists results as evidence records.
Designed to run as a periodic ARQ background job.
"""

import logging
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger(__name__)


class FleetIngestionService:
    """Orchestrates periodic evidence ingestion for a fleet of assets."""

    def __init__(self, org_id: str | None = None):
        self.org_id = org_id
        self._stats = {"processed": 0, "skipped": 0, "errors": 0}

    async def ingest_fleet(self, limit: int = 500) -> dict[str, Any]:
        """Run a single ingestion pass for all active assets in the org.

        Returns summary stats of the ingestion run.
        """
        from db.base import async_session_factory
        from db.repository import AssetRepository, EvidenceRepository

        self._stats = {"processed": 0, "skipped": 0, "errors": 0}

        async with async_session_factory() as session:
            asset_repo = AssetRepository(session)
            evidence_repo = EvidenceRepository(session)

            # Get all active assets with NORAD IDs for this org
            assets = await asset_repo.list_fleet_assets(
                org_id=self.org_id,
                limit=limit,
            )

            for asset in assets:
                if not asset.norad_id:
                    self._stats["skipped"] += 1
                    continue

                try:
                    await self._ingest_asset(
                        session=session,
                        evidence_repo=evidence_repo,
                        asset_id=asset.id,
                        norad_id=asset.norad_id,
                        org_id=asset.org_id,
                    )
                    self._stats["processed"] += 1
                except Exception as exc:
                    log.warning(
                        "Fleet ingestion failed for asset %s (NORAD %s): %s",
                        asset.id,
                        asset.norad_id,
                        exc,
                    )
                    self._stats["errors"] += 1

        return {
            "org_id": self.org_id,
            "total_assets": len(assets),
            **self._stats,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _ingest_asset(
        self,
        *,
        session,
        evidence_repo,
        asset_id: str,
        norad_id: str,
        org_id: str | None,
    ) -> None:
        """Ingest orbital data, conjunction risk, and space weather for a single asset."""

        # 1. CelesTrak orbital data
        try:
            from services.celestrak_service import lookup_by_norad_id
            orbital_data = await lookup_by_norad_id(norad_id)
            if orbital_data:
                await evidence_repo.create_record(
                    asset_id=asset_id,
                    org_id=org_id,
                    source_type="celestrak",
                    evidence_role="runtime",
                    provider="CelesTrak",
                    confidence=0.90,
                    payload_json=orbital_data if isinstance(orbital_data, dict) else {"data": str(orbital_data)},
                    tags=["fleet_ingestion", "orbital"],
                )
        except Exception as exc:
            log.debug("CelesTrak lookup failed for NORAD %s: %s", norad_id, exc)

        # 2. Conjunction risk assessment
        try:
            from services.conjunction_service import assess_conjunction_risk
            conjunction_data = await assess_conjunction_risk(norad_id)
            if conjunction_data:
                await evidence_repo.create_record(
                    asset_id=asset_id,
                    org_id=org_id,
                    source_type="conjunction_risk",
                    evidence_role="runtime",
                    provider="CelesTrak/SOCRATES",
                    confidence=0.85,
                    payload_json=conjunction_data if isinstance(conjunction_data, dict) else {"data": str(conjunction_data)},
                    tags=["fleet_ingestion", "conjunction"],
                )
        except Exception as exc:
            log.debug("Conjunction risk failed for NORAD %s: %s", norad_id, exc)

        # 3. Space weather (shared across fleet, cached)
        try:
            from services.space_weather_service import fetch_space_weather
            weather = await fetch_space_weather()
            if weather:
                weather_data = {
                    "kp_index": weather.kp_index,
                    "kp_category": weather.kp_category,
                    "solar_wind_speed_km_s": weather.solar_wind_speed_km_s,
                    "solar_wind_density_p_cm3": weather.solar_wind_density_p_cm3,
                    "proton_flux_pfu": weather.proton_flux_pfu,
                    "electron_flux": weather.electron_flux,
                    "xray_flux": weather.xray_flux,
                    "flare_class": weather.flare_class,
                    "storm_warning": weather.storm_warning,
                    "geomag_severity": weather.geomag_severity,
                }
                await evidence_repo.create_record(
                    asset_id=asset_id,
                    org_id=org_id,
                    source_type="space_weather",
                    evidence_role="runtime",
                    provider="NOAA/SWPC",
                    confidence=0.80,
                    payload_json=weather_data,
                    tags=["fleet_ingestion", "weather"],
                )
        except Exception as exc:
            log.debug("Space weather fetch failed: %s", exc)

        await session.commit()


async def run_fleet_ingestion(org_id: str | None = None, limit: int = 500) -> dict[str, Any]:
    """Convenience function for ARQ periodic job scheduling."""
    service = FleetIngestionService(org_id=org_id)
    return await service.ingest_fleet(limit=limit)
