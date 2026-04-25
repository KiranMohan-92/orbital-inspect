"""
Evidence fusion service — collects and merges evidence from multiple sources.

Currently supports:
  - Current and historical orbital data from CelesTrak
  - Optional Space-Track SATCAT enrichment when credentials are configured
  - Optional UCS public reference profile ingestion when a text URL is configured
  - Public SatNOGS observation metadata
  - Prior analyses from the database
  - Enhanced space weather snapshots and forecasts from NOAA SWPC
  - ORDEM debris environment data
  - Conjunction screening from CelesTrak SOCRATES
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from models.evidence import EvidenceBundle, EvidenceItem, EvidenceQualityStatus, EvidenceSource

log = logging.getLogger(__name__)


async def build_evidence_bundle(
    satellite_id: str = "",
    norad_id: str | None = None,
    org_id: str | None = None,
    include_tle: bool = True,
    include_prior_analyses: bool = True,
    include_weather: bool = True,
    include_debris: bool = True,
    include_conjunction: bool = True,
    include_reference_profile: bool = True,
    include_rf_activity: bool = True,
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
    sat_data: dict | None = None

    if include_tle and norad_id:
        try:
            from services.celestrak_service import lookup_by_norad_id
            from services.tle_history_service import analyze_tle_history

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
                    metadata={
                        "provider": "CelesTrak",
                        "norad_id": norad_id,
                        "external_ref": f"celestrak:gp:{norad_id}:{sat_data.get('epoch', '')}",
                        "source_url": "https://celestrak.org/NORAD/elements/gp.php",
                        "tags": ["orbital_context", "public"],
                    },
                ))

            tle_analysis = await analyze_tle_history(norad_id, days=90)
            if tle_analysis.sample_count > 0:
                bundle.add_item(EvidenceItem(
                    source=EvidenceSource.TLE_HISTORY,
                    data_type="application/json",
                    timestamp=tle_analysis.history_end,
                    description=(
                        f"90-day orbital health analysis — "
                        f"{tle_analysis.overall_health_score}/100 ({tle_analysis.health_rating})"
                    ),
                    confidence=0.9 if tle_analysis.sample_count >= 5 else 0.7,
                    payload={
                        "analysis_window_days": tle_analysis.analysis_window_days,
                        "sample_count": tle_analysis.sample_count,
                        "history_start": tle_analysis.history_start,
                        "history_end": tle_analysis.history_end,
                        "altitude_stability_km": tle_analysis.altitude_stability_km,
                        "orbit_decay_rate_km_per_day": tle_analysis.orbit_decay_rate_km_per_day,
                        "eccentricity_stability": tle_analysis.eccentricity_stability,
                        "inclination_drift_deg_per_day": tle_analysis.inclination_drift_deg_per_day,
                        "maneuver_count": tle_analysis.maneuver_count,
                        "maneuver_frequency_90d": tle_analysis.maneuver_frequency_90d,
                        "minimum_altitude_km": tle_analysis.minimum_altitude_km,
                        "maximum_altitude_km": tle_analysis.maximum_altitude_km,
                        "overall_health_score": tle_analysis.overall_health_score,
                        "health_rating": tle_analysis.health_rating,
                        "detected_maneuvers": [
                            {
                                "epoch": event.epoch,
                                "delta_altitude_km": event.delta_altitude_km,
                                "delta_eccentricity": event.delta_eccentricity,
                                "delta_inclination_deg": event.delta_inclination_deg,
                                "estimated_delta_v_m_s": event.estimated_delta_v_m_s,
                                "severity": event.severity,
                            }
                            for event in tle_analysis.detected_maneuvers[:10]
                        ],
                    },
                    metadata={
                        "provider": "CelesTrak",
                        "norad_id": norad_id,
                        "external_ref": f"celestrak:history:{norad_id}:{tle_analysis.history_end}",
                        "source_url": "https://celestrak.org/NORAD/documentation/gp-data-formats.php",
                        "tags": ["orbital_context", "historical", "public"],
                    },
                ))
        except Exception as exc:
            log.warning("TLE evidence fetch failed", extra={"error": str(exc)})
            bundle.add_quality_gap(
                source=EvidenceSource.TLE_HISTORY,
                status=EvidenceQualityStatus.FETCH_FAILED,
                description="TLE history evidence fetch failed",
                error=str(exc),
            )

    if include_reference_profile and norad_id:
        try:
            from services.space_track_service import lookup_satcat_by_norad_id
            from services.ucs_service import lookup_by_norad_id as lookup_ucs_by_norad_id

            satcat = await lookup_satcat_by_norad_id(norad_id)
            if satcat:
                bundle.add_item(EvidenceItem(
                    source=EvidenceSource.REFERENCE_PROFILE,
                    data_type="application/json",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    description=f"Space-Track SATCAT profile for NORAD {norad_id}",
                    confidence=0.9,
                    payload=satcat,
                    metadata={
                        "provider": "Space-Track",
                        "external_ref": f"space_track:satcat:{norad_id}",
                        "source_url": "https://www.space-track.org/documentation",
                        "tags": ["baseline", "catalog", "public"],
                    },
                ))

            ucs_profile = await lookup_ucs_by_norad_id(norad_id)
            if ucs_profile:
                bundle.add_item(EvidenceItem(
                    source=EvidenceSource.REFERENCE_PROFILE,
                    data_type="application/json",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    description=(
                        f"Public reference profile — {ucs_profile.get('purpose') or 'mission metadata'}"
                    ),
                    confidence=0.78,
                    payload=ucs_profile,
                    metadata={
                        "provider": "UCS",
                        "external_ref": f"ucs:{norad_id}",
                        "source_url": "https://www.ucs.org/resources/satellite-database",
                        "tags": ["baseline", "reference", "public"],
                    },
                ))
        except Exception as exc:
            log.warning("Reference profile evidence fetch failed", extra={"error": str(exc)})
            bundle.add_quality_gap(
                source=EvidenceSource.REFERENCE_PROFILE,
                status=EvidenceQualityStatus.FETCH_FAILED,
                description="Reference profile evidence fetch failed",
                error=str(exc),
                required_for_decision=False,
                mission_relevance="supporting",
            )

    if include_prior_analyses and norad_id:
        try:
            from db.base import async_session_factory
            from db.repository import AnalysisRepository

            async with async_session_factory() as session:
                repo = AnalysisRepository(session)
                analyses, _total = await repo.list_analyses(org_id=org_id, limit=25)

                matching = [
                    analysis for analysis in analyses
                    if analysis.norad_id == norad_id and analysis.status in {"completed", "completed_partial"}
                ]
                bundle.prior_analyses_count = len(matching)

                for analysis in matching[:5]:
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
                        metadata={
                            "analysis_id": analysis.id,
                            "provider": "Orbital Inspect",
                            "external_ref": f"analysis:{analysis.id}",
                            "tags": ["historical", "internal"],
                        },
                    ))
        except ImportError:
            log.info("Database not available for prior analysis evidence")
        except Exception as exc:
            log.warning("Prior analysis evidence fetch failed", extra={"error": str(exc)})
            bundle.add_quality_gap(
                source=EvidenceSource.PRIOR_ANALYSIS,
                status=EvidenceQualityStatus.FETCH_FAILED,
                description="Prior analysis evidence fetch failed",
                error=str(exc),
                required_for_decision=False,
                mission_relevance="supporting",
            )

    if include_rf_activity and norad_id:
        try:
            from services.satnogs_service import fetch_recent_observations, summarize_observations

            observations = await fetch_recent_observations(norad_id)
            if observations:
                summary = summarize_observations(observations)
                bundle.add_item(EvidenceItem(
                    source=EvidenceSource.RF_ACTIVITY,
                    data_type="application/json",
                    timestamp=summary.get("latest_start") or datetime.now(timezone.utc).isoformat(),
                    description=(
                        f"SatNOGS observation activity — {summary['observation_count']} recent observations"
                    ),
                    confidence=0.62,
                    payload={
                        **summary,
                        "observations": observations[:5],
                    },
                    metadata={
                        "provider": "SatNOGS",
                        "external_ref": f"satnogs:{norad_id}:{summary.get('latest_start') or 'latest'}",
                        "source_url": "https://network.satnogs.org/",
                        "license": "CC BY-SA",
                        "redistribution_policy": "public observation metadata",
                        "tags": ["rf_activity", "public"],
                    },
                ))
        except Exception as exc:
            log.warning("RF activity evidence fetch failed", extra={"error": str(exc)})
            bundle.add_quality_gap(
                source=EvidenceSource.RF_ACTIVITY,
                status=EvidenceQualityStatus.FETCH_FAILED,
                description="RF activity evidence fetch failed",
                error=str(exc),
                required_for_decision=False,
                mission_relevance="supporting",
            )

    if include_weather:
        try:
            from services.enhanced_weather_service import fetch_enhanced_space_weather

            weather = await fetch_enhanced_space_weather()
            bundle.add_item(EvidenceItem(
                source=EvidenceSource.SPACE_WEATHER,
                data_type="application/json",
                timestamp=datetime.now(timezone.utc).isoformat(),
                description=(
                    f"Enhanced space weather — Kp {weather.kp_index} ({weather.kp_category}), "
                    f"Bz {weather.bz_nt:.1f} nT"
                ),
                confidence=0.98,
                payload={
                    "kp_index": weather.kp_index,
                    "kp_category": weather.kp_category,
                    "solar_wind_speed_km_s": weather.solar_wind_speed_km_s,
                    "solar_wind_density_p_cm3": weather.solar_wind_density_p_cm3,
                    "proton_flux_pfu": weather.proton_flux_pfu,
                    "xray_flux": weather.xray_flux,
                    "flare_class": weather.flare_class,
                    "storm_warning": weather.storm_warning,
                    "geomag_severity": weather.geomag_severity,
                    "bz_nt": weather.bz_nt,
                    "bt_nt": weather.bt_nt,
                    "bz_orientation": weather.bz_orientation,
                    "geoeffective": weather.geoeffective,
                    "highest_alert_level": weather.highest_alert_level,
                    "active_alert_count": len(weather.active_alerts),
                    "active_alerts": weather.active_alerts[:5],
                    "three_day_forecast": weather.three_day_forecast,
                    "twenty_seven_day_outlook": weather.twenty_seven_day_outlook,
                    "data_sources": weather.data_sources or [],
                },
                metadata={
                    "provider": "NOAA SWPC",
                    "source_url": "https://services.swpc.noaa.gov/",
                    "external_ref": f"noaa_swpc:{datetime.now(timezone.utc).date().isoformat()}",
                    "tags": ["environment", "public"],
                },
            ))
        except Exception as exc:
            log.warning("Space weather evidence fetch failed", extra={"error": str(exc)})
            bundle.add_quality_gap(
                source=EvidenceSource.SPACE_WEATHER,
                status=EvidenceQualityStatus.FETCH_FAILED,
                description="Space weather evidence fetch failed",
                error=str(exc),
            )

    if include_debris and norad_id:
        try:
            from services.celestrak_service import lookup_by_norad_id
            from services.ordem_service import get_debris_severity, lookup_debris_flux

            sat_data = sat_data or await lookup_by_norad_id(norad_id)
            altitude_km = sat_data.get("altitude_avg_km") if sat_data else None

            if altitude_km:
                flux = lookup_debris_flux(altitude_km)
                if flux:
                    bundle.add_item(EvidenceItem(
                        source=EvidenceSource.DEBRIS_ENVIRONMENT,
                        data_type="application/json",
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        description=f"Debris environment at {altitude_km:.0f}km — {get_debris_severity(altitude_km)}",
                        confidence=0.9,
                        payload={
                            "altitude_km": altitude_km,
                            "flux_1mm": flux.flux_1mm,
                            "flux_1cm": flux.flux_1cm,
                            "flux_10cm": flux.flux_10cm,
                            "collision_prob_per_year": flux.collision_prob_per_year,
                            "cataloged_objects": flux.cataloged_objects,
                            "severity": get_debris_severity(altitude_km),
                        },
                        metadata={
                            "provider": "NASA ORDEM 4.0",
                            "external_ref": f"ordem:{norad_id}:{datetime.now(timezone.utc).date().isoformat()}",
                            "tags": ["environment", "public"],
                        },
                    ))
        except Exception as exc:
            log.warning("Debris evidence fetch failed", extra={"error": str(exc)})
            bundle.add_quality_gap(
                source=EvidenceSource.DEBRIS_ENVIRONMENT,
                status=EvidenceQualityStatus.FETCH_FAILED,
                description="Debris environment evidence fetch failed",
                error=str(exc),
            )

    if include_conjunction and norad_id:
        try:
            from services.conjunction_service import assess_conjunction_risk

            conjunction = await assess_conjunction_risk(norad_id)
            description = "Conjunction screening — no recent close approaches found"
            if conjunction.event_count > 0:
                description = (
                    f"Conjunction screening — score {conjunction.conjunction_risk_score}/100, "
                    f"min miss {conjunction.minimum_miss_distance_km:.2f} km"
                )

            bundle.add_item(EvidenceItem(
                source=EvidenceSource.CONJUNCTION_RISK,
                data_type="application/json",
                timestamp=datetime.now(timezone.utc).isoformat(),
                description=description,
                confidence=0.85 if conjunction.event_count > 0 else 0.65,
                payload={
                    "event_count": conjunction.event_count,
                    "minimum_miss_distance_km": conjunction.minimum_miss_distance_km,
                    "average_miss_distance_km": conjunction.average_miss_distance_km,
                    "conjunction_risk_score": conjunction.conjunction_risk_score,
                    "miss_distance_history_km": conjunction.miss_distance_history_km,
                    "most_threatening_objects": conjunction.most_threatening_objects,
                    "events": [
                        {
                            "tca": event.tca,
                            "miss_distance_km": event.miss_distance_km,
                            "relative_speed_km_s": event.relative_speed_km_s,
                            "collision_probability": event.collision_probability,
                            "counterparty_norad_id": event.counterparty_norad_id,
                            "counterparty_name": event.counterparty_name,
                            "is_debris": event.is_debris,
                            "severity": event.severity,
                        }
                        for event in conjunction.events[:10]
                    ],
                },
                metadata={
                    "provider": conjunction.data_source,
                    "norad_id": norad_id,
                    "external_ref": f"conjunction:{norad_id}:{datetime.now(timezone.utc).date().isoformat()}",
                    "tags": ["conjunction", "public"],
                },
            ))
        except Exception as exc:
            log.warning("Conjunction evidence fetch failed", extra={"error": str(exc)})
            bundle.add_quality_gap(
                source=EvidenceSource.CONJUNCTION_RISK,
                status=EvidenceQualityStatus.FETCH_FAILED,
                description="Conjunction evidence fetch failed",
                error=str(exc),
            )

    timestamps = [item.timestamp for item in bundle.items if item.timestamp]
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
