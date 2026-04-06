import os

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("GEMINI_API_KEY", "test-dummy-key")

from db.base import Base
from db.models import AssetAlias, AssetReferenceProfile, Organization
from db.repository import AnalysisRepository, AssetRepository, EvidenceRepository
from services.post_analysis_service import post_analysis_complete


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_post_analysis_complete_persists_asset_reference_profile_and_aliases(session: AsyncSession):
    org = Organization(name="Reference Integration Org")
    session.add(org)
    await session.commit()
    await session.refresh(org)

    asset_repo = AssetRepository(session)
    analysis_repo = AnalysisRepository(session)
    evidence_repo = EvidenceRepository(session)

    asset = await asset_repo.resolve_or_create(
        org_id=org.id,
        norad_id="25544",
        asset_type="satellite",
        name="ISS",
    )
    analysis = await analysis_repo.create(
        org_id=org.id,
        asset_id=asset.id,
        norad_id="25544",
        asset_type="satellite",
        baseline_reference={
            "revision": "rev-a",
            "operator_asset_id": "OPS-ISS-01",
            "manufacturer_designation": "Zarya",
            "subsystem_baseline": {"solar_array": {"count": 2}},
        },
        capture_metadata={
            "operator_asset_id": "OPS-ISS-01",
        },
        evidence_completeness_pct=100.0,
        human_review_required=True,
    )
    await analysis_repo.update_fields(
        analysis.id,
        status="completed",
        insurance_risk_result={
            "risk_matrix": {"composite": 45},
            "risk_tier": "LOW",
            "underwriting_recommendation": "INSURABLE_STANDARD",
        },
    )

    ucs_record = await evidence_repo.create_record(
        org_id=org.id,
        asset_id=asset.id,
        source_type="reference_profile",
        evidence_role="reference",
        provider="UCS",
        external_ref="ucs:25544",
        payload_json={
            "norad_id": "25544",
            "satcat_id": "25544",
            "cospar_id": "1998-067A",
            "operator_name": "Multinational",
            "purpose": "Civil",
            "orbit_class": "LEO",
            "manufacturer": "Boeing",
            "power_w": 120000.0,
            "manufacturer_designation": "Zarya",
        },
        source_url="https://www.ucs.org/resources/satellite-database",
        confidence=0.78,
        tags=["baseline", "public"],
    )
    celestrak_record = await evidence_repo.create_record(
        org_id=org.id,
        asset_id=asset.id,
        source_type="celestrak",
        evidence_role="runtime",
        provider="CelesTrak",
        external_ref="celestrak:history:25544:2026-04-05T00:00:00Z",
        payload_json={
            "orbital_regime": "LEO",
            "period_min": 92.7,
        },
        source_url="https://celestrak.org/",
        confidence=0.92,
        tags=["orbital_context", "public"],
    )
    await evidence_repo.link_analysis_evidence(
        analysis_id=analysis.id,
        evidence_id=ucs_record.id,
        used_for="baseline",
    )
    await evidence_repo.link_analysis_evidence(
        analysis_id=analysis.id,
        evidence_id=celestrak_record.id,
        used_for="orbital_context",
    )

    await post_analysis_complete(analysis_id=analysis.id, session=session)

    refreshed = await analysis_repo.get(analysis.id)
    profile = (
        await session.execute(
            select(AssetReferenceProfile).where(AssetReferenceProfile.asset_id == asset.id)
        )
    ).scalar_one()
    aliases = (
        await session.execute(select(AssetAlias).where(AssetAlias.asset_id == asset.id))
    ).scalars().all()
    alias_pairs = {(alias.alias_type, alias.alias_value) for alias in aliases}

    assert refreshed.decision_status == "pending_human_review"
    assert refreshed.triage_score is not None
    assert profile.operator_name == "Multinational"
    assert profile.manufacturer == "Boeing"
    assert profile.mission_class == "Civil"
    assert profile.orbit_regime == "LEO"
    assert profile.subsystem_baseline_json["solar_array"]["count"] == 2
    assert profile.dimensions_json["power_w"] == 120000.0
    assert profile.dimensions_json["period_min"] == 92.7
    assert any(source.startswith("UCS:") for source in profile.reference_sources_json)
    assert ("operator_asset_id", "OPS-ISS-01") in alias_pairs
    assert ("cospar", "1998-067A") in alias_pairs
    assert ("manufacturer_designation", "Zarya") in alias_pairs
