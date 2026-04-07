"""Offline benchmark dataset registry service.

Defines known space-domain benchmark datasets and provides a seed function
that registers them into the database. These datasets are strictly for
offline evaluation and R&D — they must never enter runtime customer evidence
paths.

Known benchmarks:
  - SPEED   — Satellite Pose Estimation Challenge (ESA/DLR)
  - SPEED+  — Extended SPEED with lightbox imagery (Stanford/ESA)
  - OPS-SAT-AD — ESA OPS-SAT anomaly detection telemetry corpus
  - ESA Anomaly Telemetry — ESA ESOC spacecraft anomaly dataset
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession

from db.repository import EvidenceRepository

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class BenchmarkDatasetSpec:
    """Immutable specification for a known benchmark dataset."""

    name: str
    dataset_type: str
    source_url: str
    license: str
    version: str
    record_count: int | None
    intended_use: str
    notes: str


KNOWN_BENCHMARKS: list[BenchmarkDatasetSpec] = [
    BenchmarkDatasetSpec(
        name="SPEED",
        dataset_type="pose_estimation",
        source_url="https://zenodo.org/records/6327547",
        license="CC-BY-4.0",
        version="1.0",
        record_count=15000,
        intended_use="offline_eval",
        notes=(
            "Satellite Pose Estimation Challenge dataset. "
            "Synthetic and real images of the TANGO satellite from the PRISMA mission. "
            "Suitable for pose estimation model benchmarking."
        ),
    ),
    BenchmarkDatasetSpec(
        name="SPEED+",
        dataset_type="pose_estimation",
        source_url="https://zenodo.org/records/5588480",
        license="CC-BY-4.0",
        version="1.0",
        record_count=59960,
        intended_use="offline_eval",
        notes=(
            "Extended SPEED dataset with lightbox-captured imagery. "
            "Includes synthetic, lightbox, and sunlamp domains for domain adaptation "
            "research in satellite pose estimation."
        ),
    ),
    BenchmarkDatasetSpec(
        name="OPS-SAT-AD",
        dataset_type="anomaly_detection",
        source_url="https://zenodo.org/records/8105576",
        license="CC-BY-4.0",
        version="1.0",
        record_count=None,
        intended_use="offline_eval",
        notes=(
            "ESA OPS-SAT spacecraft anomaly detection telemetry corpus. "
            "Contains labeled anomalous and nominal telemetry sequences from ESA's "
            "OPS-SAT nanosatellite. For anomaly detection model evaluation."
        ),
    ),
    BenchmarkDatasetSpec(
        name="ESA Anomaly Telemetry",
        dataset_type="anomaly_detection",
        source_url="https://zenodo.org/records/3625914",
        license="CC-BY-4.0",
        version="1.0",
        record_count=None,
        intended_use="offline_eval",
        notes=(
            "ESA ESOC spacecraft anomaly telemetry dataset. "
            "Real spacecraft telemetry with labeled anomalies from ESA missions. "
            "Suitable for time-series anomaly detection benchmarking."
        ),
    ),
]


async def seed_benchmark_datasets(session: AsyncSession) -> list[dict]:
    """Register all known benchmark datasets. Upserts — safe to call repeatedly.

    Returns a list of dicts summarising each registered dataset.
    """
    evidence_repo = EvidenceRepository(session)
    results: list[dict] = []

    for spec in KNOWN_BENCHMARKS:
        dataset = await evidence_repo.register_dataset(
            name=spec.name,
            dataset_type=spec.dataset_type,
            source_url=spec.source_url,
            license=spec.license,
            intended_use=spec.intended_use,
            version=spec.version,
            record_count=spec.record_count,
            notes=spec.notes,
        )
        results.append({
            "id": dataset.id,
            "name": dataset.name,
            "dataset_type": dataset.dataset_type,
            "version": dataset.version,
            "intended_use": dataset.intended_use,
        })
        log.info("Registered benchmark dataset: %s v%s", spec.name, spec.version)

    return results
