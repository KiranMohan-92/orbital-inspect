import os
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("GEMINI_API_KEY", "test-dummy-key")

from db.base import Base
from db.models import Analysis, Asset, Organization
from db.repository import AnalysisRepository, AssetRepository, EvidenceRepository


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
async def test_create_and_link_reusable_evidence_record(session: AsyncSession):
    org = Organization(name="Orbital Test Org")
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
    )

    record = await evidence_repo.create_record(
        org_id=org.id,
        asset_id=asset.id,
        source_type="celestrak",
        evidence_role="runtime",
        provider="CelesTrak",
        external_ref="25544:2026-04-05T00:00:00Z",
        payload_json={"orbit_regime": "LEO"},
        source_url="https://celestrak.org/",
        confidence=0.95,
        tags=["orbital_context"],
    )
    link = await evidence_repo.link_analysis_evidence(
        analysis_id=analysis.id,
        evidence_id=record.id,
        used_for="orbital_context",
    )
    linked = await evidence_repo.list_analysis_evidence(analysis_id=analysis.id)

    assert link.analysis_id == analysis.id
    assert len(linked) == 1
    linked_link, linked_record = linked[0]
    assert linked_link.used_for == "orbital_context"
    assert linked_record.source_type == "celestrak"
    assert linked_record.payload_json["orbit_regime"] == "LEO"


@pytest.mark.asyncio
async def test_upsert_asset_reference_profile_updates_existing_record(session: AsyncSession):
    org = Organization(name="Reference Org")
    session.add(org)
    await session.commit()
    await session.refresh(org)

    asset_repo = AssetRepository(session)
    evidence_repo = EvidenceRepository(session)

    asset = await asset_repo.resolve_or_create(
        org_id=org.id,
        norad_id="43013",
        asset_type="satellite",
        name="BaselineSat",
    )
    first = await evidence_repo.upsert_asset_reference_profile(
        asset_id=asset.id,
        org_id=org.id,
        operator_name="Operator A",
        mission_class="communications",
        orbit_regime="GEO",
        reference_sources_json=["ucs"],
    )
    second = await evidence_repo.upsert_asset_reference_profile(
        asset_id=asset.id,
        operator_name="Operator A",
        manufacturer="Maxar",
        reference_revision="rev-b",
        dimensions_json={"span_m": 35.0},
        subsystem_baseline_json={"solar_array": {"count": 2}},
        reference_sources_json=["ucs", "nasa_doc"],
        last_verified_at=datetime.now(timezone.utc),
    )

    assert first.id == second.id
    assert second.manufacturer == "Maxar"
    assert second.reference_revision == "rev-b"
    assert second.dimensions_json["span_m"] == 35.0
    assert second.reference_sources_json == ["ucs", "nasa_doc"]


@pytest.mark.asyncio
async def test_ingest_runs_and_dataset_registry_are_persisted(session: AsyncSession):
    evidence_repo = EvidenceRepository(session)

    run = await evidence_repo.start_ingest_run(
        source_type="space_track",
        rate_limit_window="daily",
        cursor_or_checkpoint="2026-04-05",
    )
    await evidence_repo.finish_ingest_run(
        run.id,
        status="completed",
        records_created=12,
        records_updated=3,
        cursor_or_checkpoint="2026-04-06",
    )
    dataset = await evidence_repo.register_dataset(
        name="SPEED+",
        dataset_type="pose",
        source_url="https://zenodo.org/records/5588480",
        license="CC-BY-4.0",
        version="1.0",
        notes="Offline evaluation only",
    )
    updated_dataset = await evidence_repo.register_dataset(
        name="SPEED+",
        dataset_type="pose",
        source_url="https://zenodo.org/records/5588480",
        license="CC-BY-4.0",
        version="1.1",
        notes="Updated metadata",
    )

    refreshed_run = await session.get(type(run), run.id)
    assert refreshed_run.status == "completed"
    assert refreshed_run.records_created == 12
    assert refreshed_run.cursor_or_checkpoint == "2026-04-06"
    assert dataset.id == updated_dataset.id
    assert updated_dataset.version == "1.1"
    assert updated_dataset.notes == "Updated metadata"


@pytest.mark.asyncio
async def test_resolve_or_create_matches_operator_asset_id_alias(session: AsyncSession):
    org = Organization(name="Alias Org")
    session.add(org)
    await session.commit()
    await session.refresh(org)

    asset_repo = AssetRepository(session)

    first = await asset_repo.resolve_or_create(
        org_id=org.id,
        norad_id=None,
        asset_type="station_module",
        name="Hab-1",
        alias_candidates={
            "operator_asset_id": "AXM-HAB-01",
            "cospar": "2026-001A",
        },
    )
    second = await asset_repo.resolve_or_create(
        org_id=org.id,
        norad_id=None,
        asset_type="station_module",
        name="Axiom Habitat",
        alias_candidates={
            "operator_asset_id": "AXM-HAB-01",
        },
    )

    assert first.id == second.id
    assert second.identity_source == "operator_asset_id"
