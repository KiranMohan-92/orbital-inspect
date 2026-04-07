"""Tests for Phase 5: Offline Evaluation Layer.

Covers:
  - Benchmark dataset registration and upsert semantics
  - Dataset listing with filters
  - Dataset detail retrieval
  - Runtime/offline_eval separation guardrail
  - Seed service registers all known benchmarks
  - New model columns (record_count, checksum_sha256)
"""

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
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def org(session: AsyncSession) -> Organization:
    org = Organization(name="Eval Test Org")
    session.add(org)
    await session.commit()
    await session.refresh(org)
    return org


# ── Dataset Registration ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_register_dataset_with_new_columns(session: AsyncSession):
    """record_count and checksum_sha256 are persisted on registration."""
    repo = EvidenceRepository(session)
    dataset = await repo.register_dataset(
        name="SPEED+",
        dataset_type="pose_estimation",
        source_url="https://zenodo.org/records/5588480",
        license="CC-BY-4.0",
        version="1.0",
        record_count=59960,
        checksum_sha256="abc123def456",
        notes="Pose estimation benchmark",
    )
    assert dataset.record_count == 59960
    assert dataset.checksum_sha256 == "abc123def456"
    assert dataset.intended_use == "offline_eval"


@pytest.mark.asyncio
async def test_register_dataset_upsert_updates_version_and_count(session: AsyncSession):
    """Re-registering the same dataset name updates version and metadata."""
    repo = EvidenceRepository(session)
    first = await repo.register_dataset(
        name="OPS-SAT-AD",
        dataset_type="anomaly_detection",
        source_url="https://zenodo.org/records/8105576",
        version="1.0",
        record_count=1000,
    )
    second = await repo.register_dataset(
        name="OPS-SAT-AD",
        dataset_type="anomaly_detection",
        source_url="https://zenodo.org/records/8105576",
        version="2.0",
        record_count=2500,
        checksum_sha256="newchecksum",
    )
    assert first.id == second.id
    assert second.version == "2.0"
    assert second.record_count == 2500
    assert second.checksum_sha256 == "newchecksum"


# ── Dataset Listing & Detail ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_datasets_returns_all_registered(session: AsyncSession):
    repo = EvidenceRepository(session)
    await repo.register_dataset(
        name="Dataset A",
        dataset_type="pose_estimation",
        source_url="https://example.com/a",
        version="1.0",
    )
    await repo.register_dataset(
        name="Dataset B",
        dataset_type="anomaly_detection",
        source_url="https://example.com/b",
        version="1.0",
    )
    all_datasets = await repo.list_datasets()
    assert len(all_datasets) == 2
    names = {d.name for d in all_datasets}
    assert names == {"Dataset A", "Dataset B"}


@pytest.mark.asyncio
async def test_list_datasets_filters_by_type(session: AsyncSession):
    repo = EvidenceRepository(session)
    await repo.register_dataset(
        name="Pose DS",
        dataset_type="pose_estimation",
        source_url="https://example.com/pose",
        version="1.0",
    )
    await repo.register_dataset(
        name="Anomaly DS",
        dataset_type="anomaly_detection",
        source_url="https://example.com/anomaly",
        version="1.0",
    )
    pose_only = await repo.list_datasets(dataset_type="pose_estimation")
    assert len(pose_only) == 1
    assert pose_only[0].name == "Pose DS"


@pytest.mark.asyncio
async def test_list_datasets_filters_by_intended_use(session: AsyncSession):
    repo = EvidenceRepository(session)
    await repo.register_dataset(
        name="Eval DS",
        dataset_type="anomaly_detection",
        source_url="https://example.com/eval",
        intended_use="offline_eval",
        version="1.0",
    )
    await repo.register_dataset(
        name="Research DS",
        dataset_type="anomaly_detection",
        source_url="https://example.com/research",
        intended_use="research",
        version="1.0",
    )
    eval_only = await repo.list_datasets(intended_use="offline_eval")
    assert len(eval_only) == 1
    assert eval_only[0].name == "Eval DS"


@pytest.mark.asyncio
async def test_get_dataset_by_id(session: AsyncSession):
    repo = EvidenceRepository(session)
    created = await repo.register_dataset(
        name="Detail DS",
        dataset_type="pose_estimation",
        source_url="https://example.com/detail",
        version="3.0",
        record_count=100,
    )
    fetched = await repo.get_dataset(created.id)
    assert fetched is not None
    assert fetched.name == "Detail DS"
    assert fetched.version == "3.0"
    assert fetched.record_count == 100


@pytest.mark.asyncio
async def test_get_dataset_returns_none_for_missing_id(session: AsyncSession):
    repo = EvidenceRepository(session)
    result = await repo.get_dataset("nonexistent_id_12345678")
    assert result is None


# ── Runtime / Offline-Eval Separation Guardrail ──────────────────────


@pytest.mark.asyncio
async def test_offline_eval_evidence_cannot_be_linked_to_analysis(
    session: AsyncSession, org: Organization
):
    """The guardrail must prevent offline_eval evidence from being linked
    to a runtime analysis — this is the key safety invariant of Phase 5."""
    asset_repo = AssetRepository(session)
    analysis_repo = AnalysisRepository(session)
    evidence_repo = EvidenceRepository(session)

    asset = await asset_repo.resolve_or_create(
        org_id=org.id, norad_id="25544", asset_type="satellite", name="ISS",
    )
    analysis = await analysis_repo.create(
        org_id=org.id, asset_id=asset.id, norad_id="25544",
    )
    offline_record = await evidence_repo.create_record(
        org_id=org.id,
        asset_id=asset.id,
        source_type="benchmark_corpus",
        evidence_role="offline_eval",
        provider="SPEED+",
        payload_json={"domain": "lightbox"},
    )

    with pytest.raises(ValueError, match="offline_eval"):
        await evidence_repo.link_analysis_evidence(
            analysis_id=analysis.id,
            evidence_id=offline_record.id,
            used_for="pose_benchmark",
        )


@pytest.mark.asyncio
async def test_runtime_evidence_can_still_be_linked_to_analysis(
    session: AsyncSession, org: Organization
):
    """Normal runtime evidence linking must not be broken by the guardrail."""
    asset_repo = AssetRepository(session)
    analysis_repo = AnalysisRepository(session)
    evidence_repo = EvidenceRepository(session)

    asset = await asset_repo.resolve_or_create(
        org_id=org.id, norad_id="25544", asset_type="satellite", name="ISS",
    )
    analysis = await analysis_repo.create(
        org_id=org.id, asset_id=asset.id, norad_id="25544",
    )
    runtime_record = await evidence_repo.create_record(
        org_id=org.id,
        asset_id=asset.id,
        source_type="celestrak",
        evidence_role="runtime",
        provider="CelesTrak",
        payload_json={"orbit_regime": "LEO"},
    )

    link = await evidence_repo.link_analysis_evidence(
        analysis_id=analysis.id,
        evidence_id=runtime_record.id,
        used_for="orbital_context",
    )
    assert link.analysis_id == analysis.id
    assert link.evidence_id == runtime_record.id


@pytest.mark.asyncio
async def test_validate_evidence_not_offline_eval(
    session: AsyncSession, org: Organization
):
    """Direct validation helper returns correct booleans."""
    evidence_repo = EvidenceRepository(session)

    runtime = await evidence_repo.create_record(
        org_id=org.id, asset_id=None,
        source_type="celestrak", evidence_role="runtime",
    )
    offline = await evidence_repo.create_record(
        org_id=org.id, asset_id=None,
        source_type="benchmark", evidence_role="offline_eval",
    )
    reference = await evidence_repo.create_record(
        org_id=org.id, asset_id=None,
        source_type="ucs", evidence_role="reference",
    )

    assert await evidence_repo.validate_evidence_not_offline_eval(runtime.id) is True
    assert await evidence_repo.validate_evidence_not_offline_eval(offline.id) is False
    assert await evidence_repo.validate_evidence_not_offline_eval(reference.id) is True


# ── Seed Service ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_seed_benchmark_datasets_registers_all_known(session: AsyncSession):
    from services.dataset_registry_service import seed_benchmark_datasets, KNOWN_BENCHMARKS

    results = await seed_benchmark_datasets(session)
    assert len(results) == len(KNOWN_BENCHMARKS)

    repo = EvidenceRepository(session)
    all_datasets = await repo.list_datasets()
    assert len(all_datasets) == len(KNOWN_BENCHMARKS)

    names = {d.name for d in all_datasets}
    expected_names = {spec.name for spec in KNOWN_BENCHMARKS}
    assert names == expected_names


@pytest.mark.asyncio
async def test_seed_benchmark_datasets_is_idempotent(session: AsyncSession):
    """Running seed twice must not create duplicates."""
    from services.dataset_registry_service import seed_benchmark_datasets, KNOWN_BENCHMARKS

    first = await seed_benchmark_datasets(session)
    second = await seed_benchmark_datasets(session)

    assert len(first) == len(second)
    first_ids = {r["id"] for r in first}
    second_ids = {r["id"] for r in second}
    assert first_ids == second_ids

    repo = EvidenceRepository(session)
    all_datasets = await repo.list_datasets()
    assert len(all_datasets) == len(KNOWN_BENCHMARKS)


@pytest.mark.asyncio
async def test_seed_datasets_all_marked_offline_eval(session: AsyncSession):
    """Every seeded benchmark must carry intended_use='offline_eval'."""
    from services.dataset_registry_service import seed_benchmark_datasets

    await seed_benchmark_datasets(session)
    repo = EvidenceRepository(session)
    all_datasets = await repo.list_datasets()
    for ds in all_datasets:
        assert ds.intended_use == "offline_eval", (
            f"Dataset {ds.name} has intended_use={ds.intended_use!r}, expected 'offline_eval'"
        )
