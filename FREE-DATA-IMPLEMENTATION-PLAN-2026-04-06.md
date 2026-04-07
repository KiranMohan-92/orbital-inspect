# Orbital Inspect Free Data Implementation Plan

Generated: 2026-04-06
Status: Active execution plan

## Objective

Strengthen Orbital Inspect with free public data in a way that improves asset identity, orbital context, operator baselines, and offline evaluation without pretending public data can replace proprietary telemetry, tasking, or inspection-grade imagery.

## Guiding Rules

- Use free public data to improve context, provenance, and baselines now.
- Keep runtime customer evidence separate from offline benchmark datasets.
- Do not treat SatNOGS as operator telemetry.
- Do not build the product thesis around scraping random public imagery.
- Keep the schema partnership-ready for future telemetry, tasking, and partner imagery.

## In Scope Now

- CelesTrak orbital and TLE-history enrichment
- Optional Space-Track SATCAT enrichment when credentials are configured
- UCS Satellite Database baseline/reference enrichment
- SatNOGS observation summaries as low-confidence RF-activity hints
- Persistent reusable evidence records and analysis-to-evidence provenance links
- Canonical asset reference profiles synthesized from analysis baseline input and linked public evidence
- Dataset registry foundation for offline anomaly and pose benchmarks

## Out of Scope Now

- Partner tasking integrations
- Proprietary operator telemetry ingestion
- Commercial non-Earth imagery access as a hard dependency
- Geometry/metrology claims from public datasets alone
- Building a public multi-epoch inspection corpus from scraped web imagery

## Phase Plan

### Phase 1: Evidence Persistence Foundation
Status: Completed

Deliverables:
- Add persistent `evidence_records`
- Add `analysis_evidence_links`
- Add `asset_reference_profiles`
- Add `ingest_runs`
- Add `dataset_registry`
- Add repository support for reusable evidence and reference-profile persistence
- Add migration coverage and repository tests

Primary files:
- `backend/db/models.py`
- `backend/db/repository.py`
- `backend/alembic/versions/20260405_0004_evidence_persistence_foundation.py`
- `backend/tests/test_evidence_repository.py`

Acceptance:
- Evidence is reusable across analyses
- Provenance is explicit rather than embedded only in per-analysis JSON
- Reference profiles and dataset metadata are persisted independently of a single analysis

### Phase 2: Free Runtime Ingestion
Status: Completed

Deliverables:
- Add public-source adapters for Space-Track, UCS, and SatNOGS
- Extend evidence bundle construction to include public orbital/reference/RF context
- Persist analysis evidence bundles into reusable evidence records and provenance links
- Classify evidence into `runtime`, `reference`, and `offline_eval`

Primary files:
- `backend/services/space_track_service.py`
- `backend/services/ucs_service.py`
- `backend/services/satnogs_service.py`
- `backend/services/evidence_ingest_service.py`
- `backend/services/evidence_service.py`
- `backend/main.py`
- `backend/tests/test_public_data_services.py`

Acceptance:
- Analyses can be enriched with CelesTrak plus optional Space-Track/UCS/SatNOGS data
- Public-source provenance is persisted
- Failures degrade gracefully instead of breaking analysis creation

### Phase 3: Canonical Asset Baselines
Status: Completed

Deliverables:
- Synthesize canonical asset reference profiles from analysis baseline input plus linked public evidence
- Extend canonical alias support for operator asset IDs, COSPAR identifiers, SATCAT IDs, and manufacturer designations
- Reassign linked evidence to canonical assets after post-analysis identity resolution
- Keep reference-profile accumulation in the durable asset model, not only on the individual analysis

Primary files:
- `backend/services/post_analysis_service.py`
- `backend/db/repository.py`
- `backend/main.py`
- `backend/services/space_track_service.py`
- `backend/services/ucs_service.py`
- `backend/tests/test_reference_profile_integration.py`

Acceptance:
- Asset baselines accumulate over time
- Canonical assets can be matched through stronger alias sets, not only NORAD IDs
- Reference profiles are derived from real persisted evidence, not ad hoc side data

### Phase 4: Product Integration
Status: In progress

Deliverables:
- Expose evidence summaries, provenance, and reference-profile context through analysis and asset-facing APIs
- Surface public/reference evidence clearly in operator-facing UI
- Distinguish public context, user-supplied telemetry, and future partner data visually and semantically
- Add operator-facing visibility into source confidence and provenance

Planned backend areas:
- `backend/main.py`
- `backend/api/portfolio.py`
- possible dedicated evidence API surface

Planned frontend areas:
- `frontend/src/components/analysis/IntelligenceReport.tsx`
- portfolio/asset detail surfaces

Acceptance:
- Operators can see what evidence came from where
- The UI does not imply public data equals operator telemetry
- Asset reference profile context is visible where it affects decisions and triage

### Phase 5: Offline Evaluation Layer
Status: Completed

Deliverables:
- Register offline benchmark datasets such as ESA anomaly, OPS-SAT-AD, SPEED, and SPEED+
- Keep benchmark datasets out of runtime customer evidence paths
- Add metadata scripts and tests for dataset registration/versioning
- Extend DatasetRegistry model with record_count and checksum_sha256 columns
- Add repository guardrail blocking offline_eval evidence from runtime analysis linking
- Add dataset listing, detail, and filtering APIs
- Add seed service and CLI script for benchmark dataset registration

Primary files:
- `backend/db/models.py` (DatasetRegistry extended)
- `backend/db/repository.py` (list_datasets, get_dataset, validate_evidence_not_offline_eval, guardrail in link_analysis_evidence)
- `backend/services/dataset_registry_service.py` (benchmark specs, seed function)
- `backend/api/datasets.py` (GET /api/datasets, GET /api/datasets/{id}, POST /api/datasets/seed)
- `backend/scripts/seed_benchmark_datasets.py` (CLI seeder)
- `backend/alembic/versions/20260407_0005_offline_eval_layer.py` (migration)
- `backend/tests/test_offline_eval.py` (13 tests)

Acceptance:
- Offline datasets are tracked by source, license, version, and intended use
- Runtime analysis never treats benchmark corpora as live customer evidence

### Phase 6: Partnership-Ready Interfaces
Status: Pending

Deliverables:
- Define interfaces for proprietary operator telemetry
- Define interfaces for partner imagery and tasking
- Keep implementations disabled until contracts and credentials exist

Acceptance:
- The repo is schema-ready and interface-ready for proprietary integrations
- No placeholder path silently pretends private data exists

## Execution Order

1. Phase 1 foundation
2. Phase 2 free runtime ingestion
3. Phase 3 canonical asset baselines
4. Phase 4 product integration
5. Phase 5 offline evaluation layer
6. Phase 6 partnership-ready interfaces

## Validation Standard

Each phase should close with:
- targeted regression tests for the new layer
- broader backend compatibility run
- README update when behavior or operator-facing understanding changes
- only then commit/push

## Current Progress Snapshot

Completed:
- Phase 1
- Phase 2
- Phase 3
- Phase 5

Active:
- Phase 4

Pending:
- Phase 6
