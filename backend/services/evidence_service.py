"""
Evidence fusion service — collects and merges evidence from multiple sources.

Currently supports:
  - TLE orbit history from CelesTrak
  - Prior analyses from the database
  - Space weather snapshots from NOAA SWPC
  - ORDEM debris environment data

Future:
  - Operator-uploaded telemetry
  - Maintenance records
  - Historical imagery comparison
"""

import logging
from datetime import datetime, timezone

from models.evidence import EvidenceBundle, EvidenceItem, EvidenceSource

log = logging.getLogger(__name__)


async def build_evidence_bundle(
    satellite_id: str = "",
    norad_id: str | None = None,
    include_tle: bool = True,
    include_prior_analyses: bool = True,
    include_weather: bool = True,
    include_debris: bool = True,
) -> EvidenceBundle:
    """
    Build a comprehensive evidence bundle for a satellite.

    Gathers data from all available sources and fuses into a single bundle.
    Each source is independently optional — failure to fetch one doesn't
    block others.
    """
    bundle = EvidenceBundle(
        satellite_id=satellite_id or norad_id or "unknown",
    )

    # 1. CelesTrak TLE history
    if include_tle and norad_id:
        try:
            from services.celestrak_service import lookup_by_norad_id
            sat_data = await lookup_by_norad_id(norad_id)
            if sat_data:
                bundle.satellite_name = sat_data.get("name", "")
                bundle.add_item(EvidenceItem(
                    source=EvidenceSource.TLE_HISTORY,
                    data_type="application/json",
                    timestamp=sat_data.get("epoch", ""),
                    description=f"Current TLE for NORAD {norad_id}",
                    confidence=0.95,
                    payload={
                        "name": sat_data.get("name"),
                        "altitude_avg_km": sat_data.get("altitude_avg_km"),
                        "inclination_deg": sat_data.get("inclination_deg"),
                        "orbital_regime": sat_data.get("orbital_regime"),
                        "period_min": sat_data.get("period_min"),
                        "eccentricity": sat_data.get("eccentricity"),
                        "country_code": sat_data.get("country_code"),
                        "launch_date": sat_data.get("launch_date"),
                        "rcs_size": sat_data.get("rcs_size"),
                    },
                    metadata={"provider": "CelesTrak", "norad_id": norad_id},
                ))
        except Exception as e:
            log.warning("TLE evidence fetch failed", extra={"error": str(e)})

    # 2. Prior analyses from database
    if include_prior_analyses and norad_id:
        try:
            from db.base import async_session_factory
            from db.repository import AnalysisRepository

            async with async_session_factory() as session:
                repo = AnalysisRepository(session)
                analyses, total = await repo.list_analyses(limit=10)

                # Filter to this satellite's NORAD ID
                matching = [a for a in analyses if a.norad_id == norad_id and a.status == "completed"]
                bundle.prior_analyses_count = len(matching)

                for analysis in matching[:5]:  # Last 5 analyses
                    risk_result = analysis.insurance_risk_result or {}
                    risk_tier = risk_result.get("risk_tier", "UNKNOWN")
                    bundle.prior_risk_tiers.append(risk_tier)

                    bundle.add_item(EvidenceItem(
                        source=EvidenceSource.PRIOR_ANALYSIS,
                        data_type="application/json",
                        timestamp=analysis.created_at.isoformat() if analysis.created_at else "",
                        description=f"Prior analysis — {risk_tier} risk",
                        confidence=0.9,
                        payload={
                            "analysis_id": analysis.id,
                            "risk_tier": risk_tier,
                            "report_completeness": analysis.report_completeness,
                            "underwriting_recommendation": risk_result.get("underwriting_recommendation"),
                        },
                        metadata={"analysis_id": analysis.id},
                    ))
        except ImportError:
            log.info("Database not available for prior analysis evidence")
        except Exception as e:
            log.warning("Prior analysis evidence fetch failed", extra={"error": str(e)})

    # 3. Space weather
    if include_weather:
        try:
            from services.space_weather_service import fetch_space_weather, format_weather_summary
            weather = await fetch_space_weather()
            bundle.add_item(EvidenceItem(
                source=EvidenceSource.SPACE_WEATHER,
                data_type="text/plain",
                timestamp=datetime.now(timezone.utc).isoformat(),
                description=f"Current space weather — Kp {weather.kp_index} ({weather.kp_category})",
                confidence=0.98,
                payload={
                    "kp_index": weather.kp_index,
                    "kp_category": weather.kp_category,
                    "solar_wind_speed_km_s": weather.solar_wind_speed_km_s,
                    "proton_flux_pfu": weather.proton_flux_pfu,
                    "flare_class": weather.flare_class,
                    "storm_warning": weather.storm_warning,
                    "geomag_severity": weather.geomag_severity,
                },
                metadata={"provider": "NOAA SWPC"},
            ))
        except Exception as e:
            log.warning("Space weather evidence fetch failed", extra={"error": str(e)})

    # 4. Debris environment
    if include_debris and norad_id:
        try:
            from services.celestrak_service import lookup_by_norad_id
            from services.ordem_service import lookup_debris_flux, get_debris_severity

            sat_data = await lookup_by_norad_id(norad_id) if norad_id else None
            alt = sat_data.get("altitude_avg_km") if sat_data else None

            if alt:
                flux = lookup_debris_flux(alt)
                if flux:
                    bundle.add_item(EvidenceItem(
                        source=EvidenceSource.DEBRIS_ENVIRONMENT,
                        data_type="application/json",
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        description=f"Debris environment at {alt:.0f}km — {get_debris_severity(alt)}",
                        confidence=0.9,
                        payload={
                            "altitude_km": alt,
                            "flux_1mm": flux.flux_1mm,
                            "flux_1cm": flux.flux_1cm,
                            "flux_10cm": flux.flux_10cm,
                            "collision_prob_per_year": flux.collision_prob_per_year,
                            "cataloged_objects": flux.cataloged_objects,
                            "severity": get_debris_severity(alt),
                        },
                        metadata={"provider": "NASA ORDEM 4.0"},
                    ))
        except Exception as e:
            log.warning("Debris evidence fetch failed", extra={"error": str(e)})

    # Set time bounds
    timestamps = [
        item.timestamp for item in bundle.items
        if item.timestamp
    ]
    if timestamps:
        bundle.earliest_evidence = min(timestamps)
        bundle.latest_evidence = max(timestamps)

    log.info(
        "Evidence bundle built",
        extra={
            "satellite": bundle.satellite_name or bundle.satellite_id,
            "items": bundle.total_items,
            "sources": bundle.sources_available,
        },
    )

    return bundle
