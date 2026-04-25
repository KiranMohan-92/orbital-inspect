import os
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import db.base as db_base

os.environ.setdefault("GEMINI_API_KEY", "test-dummy-key")

from db.base import Base
from db.models import Organization
from db.repository import AnalysisRepository, AssetRepository, EvidenceRepository
from main import app


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def seeded_asset_context(session_factory):
    now = datetime.now(timezone.utc)

    async with session_factory() as session:
        org = Organization(name="Asset API Test Org")
        session.add(org)
        await session.commit()
        await session.refresh(org)

        asset_repo = AssetRepository(session)
        analysis_repo = AnalysisRepository(session)
        evidence_repo = EvidenceRepository(session)

        asset = await asset_repo.resolve_or_create(
            org_id=org.id,
            norad_id="25544",
            external_asset_id="OPS-ISS-01",
            asset_type="satellite",
            name="ISS",
            operator_name="Orbital Ops",
            alias_candidates={
                "cospar": "1998-067A",
                "satcat": "25544",
                "manufacturer_designation": "Zarya",
            },
        )
        await evidence_repo.upsert_asset_reference_profile(
            asset_id=asset.id,
            org_id=org.id,
            operator_name="Orbital Ops",
            manufacturer="Orbital Works",
            mission_class="Earth Observation",
            orbit_regime="LEO",
            reference_revision="rev-phase4",
            reference_sources_json=["UCS:https://www.ucs.org/resources/satellite-database"],
            last_verified_at=now - timedelta(hours=6),
        )

        prior = await analysis_repo.create(
            org_id=org.id,
            asset_id=asset.id,
            norad_id="25544",
            asset_type="satellite",
            inspection_epoch="2026-04-04T00:00:00Z",
            target_subsystem="power",
            evidence_bundle_summary={
                "linked_evidence_count": 1,
                "sources_available": ["internal_prior_analysis"],
                "prior_analyses_count": 0,
            },
            evidence_completeness_pct=82.0,
            human_review_required=True,
        )
        await analysis_repo.update_fields(
            prior.id,
            status="completed",
            insurance_risk_result={
                "risk_tier": "MEDIUM",
                "underwriting_recommendation": "MONITOR",
            },
            decision_recommended_action="monitor",
            decision_status="approved_for_use",
            triage_score=48.2,
            triage_band="priority",
            report_completeness="PARTIAL",
            degraded=True,
            completed_at=now - timedelta(days=2),
        )

        current = await analysis_repo.create(
            org_id=org.id,
            asset_id=asset.id,
            norad_id="25544",
            asset_type="satellite",
            inspection_epoch="2026-04-06T12:00:00Z",
            target_subsystem="power",
            evidence_bundle_summary={
                "linked_evidence_count": 4,
                "sources_available": [
                    "imagery",
                    "reference_profile",
                    "celestrak",
                    "prior_analysis",
                ],
                "prior_analyses_count": 1,
            },
            evidence_completeness_pct=96.0,
            human_review_required=True,
        )
        await analysis_repo.update_fields(
            current.id,
            status="completed",
            insurance_risk_result={
                "risk_tier": "LOW",
                "underwriting_recommendation": "INSURABLE_STANDARD",
            },
            decision_recommended_action="continue_operations",
            decision_status="pending_human_review",
            triage_score=12.4,
            triage_band="routine",
            report_completeness="COMPLETE",
            degraded=False,
            completed_at=now - timedelta(hours=1),
        )
        await asset_repo.update_metadata(asset.id, current_analysis_id=current.id)

        reference_record = await evidence_repo.create_record(
            org_id=org.id,
            asset_id=asset.id,
            source_type="reference_profile",
            evidence_role="reference",
            provider="UCS",
            external_ref="ucs:25544",
            captured_at=now - timedelta(days=3),
            payload_json={
                "operator_name": "Orbital Ops",
                "purpose": "Earth Observation",
                "manufacturer": "Orbital Works",
            },
            source_url="https://www.ucs.org/resources/satellite-database",
            confidence=0.81,
            tags=["baseline", "public"],
        )
        public_runtime_record = await evidence_repo.create_record(
            org_id=org.id,
            asset_id=asset.id,
            source_type="celestrak",
            evidence_role="runtime",
            provider="CelesTrak",
            external_ref="celestrak:25544:2026-04-06T12:00:00Z",
            captured_at=now - timedelta(hours=4),
            payload_json={
                "orbital_regime": "LEO",
                "overall_health_score": 93,
            },
            source_url="https://celestrak.org/",
            confidence=0.93,
            tags=["orbital_context", "public"],
        )
        operator_runtime_record = await evidence_repo.create_record(
            org_id=org.id,
            asset_id=asset.id,
            source_type="imagery",
            evidence_role="runtime",
            provider="Operator Upload",
            external_ref="upload:img-001",
            captured_at=now - timedelta(hours=2),
            payload_json={
                "image_count": 2,
                "primary_filename": "panel-a.jpg",
            },
            artifact_uri="s3://orbital-inspect/uploads/panel-a.jpg",
            confidence=0.98,
            tags=["operator"],
        )
        internal_record = await evidence_repo.create_record(
            org_id=org.id,
            asset_id=asset.id,
            source_type="internal_prior_analysis",
            evidence_role="runtime",
            provider="Orbital Inspect",
            external_ref=f"analysis:{prior.id}",
            captured_at=now - timedelta(days=2),
            payload_json={
                "risk_tier": "MEDIUM",
                "underwriting_recommendation": "MONITOR",
            },
            confidence=0.74,
            tags=["internal"],
        )

        await evidence_repo.link_analysis_evidence(
            analysis_id=current.id,
            evidence_id=reference_record.id,
            used_for="baseline",
        )
        await evidence_repo.link_analysis_evidence(
            analysis_id=current.id,
            evidence_id=public_runtime_record.id,
            used_for="orbital_context",
        )
        await evidence_repo.link_analysis_evidence(
            analysis_id=current.id,
            evidence_id=operator_runtime_record.id,
            used_for="visual_inspection",
        )
        await evidence_repo.link_analysis_evidence(
            analysis_id=current.id,
            evidence_id=internal_record.id,
            used_for="prior_comparison",
        )
        await evidence_repo.link_analysis_evidence(
            analysis_id=prior.id,
            evidence_id=internal_record.id,
            used_for="decision_trace",
        )

        return {
            "asset_id": asset.id,
            "analysis_id": current.id,
            "prior_analysis_id": prior.id,
        }


@pytest_asyncio.fixture
async def client(session_factory, monkeypatch):
    monkeypatch.setattr(db_base, "async_session_factory", session_factory)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_get_analysis_evidence_exposes_provenance_and_reference_context(
    client,
    seeded_asset_context,
):
    response = await client.get(
        f"/api/analyses/{seeded_asset_context['analysis_id']}/evidence"
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["summary"]["linked_evidence_count"] == 4
    assert payload["summary"]["counts_by_domain"]["public"] == 2
    assert payload["summary"]["counts_by_domain"]["operator_supplied"] == 1
    assert payload["summary"]["counts_by_domain"]["internal"] == 1
    assert payload["reference_profile"]["manufacturer"] == "Orbital Works"
    assert any(alias["alias_type"] == "cospar" for alias in payload["asset"]["aliases"])

    items_by_source = {item["source_type"]: item for item in payload["items"]}
    assert items_by_source["imagery"]["source_domain"] == "operator_supplied"
    assert items_by_source["imagery"]["used_for"] == "visual_inspection"
    assert items_by_source["reference_profile"]["confidence_bucket"] == "medium"
    assert "Operator: Orbital Ops" in items_by_source["reference_profile"]["highlights"]
    assert items_by_source["celestrak"]["source_domain"] == "public"
    assert "TLE health: 93/100" in items_by_source["celestrak"]["highlights"]


@pytest.mark.asyncio
async def test_get_asset_detail_surfaces_reference_profile_and_evidence_domains(
    client,
    seeded_asset_context,
):
    response = await client.get(f"/api/assets/{seeded_asset_context['asset_id']}")

    assert response.status_code == 200
    payload = response.json()

    assert payload["asset"]["name"] == "ISS"
    assert payload["current_analysis"]["analysis_id"] == seeded_asset_context["analysis_id"]
    assert payload["reference_profile"]["orbit_regime"] == "LEO"
    assert payload["evidence_summary"]["counts_by_domain"]["public"] == 2
    assert payload["evidence_summary"]["counts_by_domain"]["operator_supplied"] == 1
    assert payload["evidence_summary"]["counts_by_domain"]["internal"] == 1
    assert "CelesTrak" in payload["evidence_summary"]["providers"]
    assert any(item["source_label"] == "Operator Upload" for item in payload["recent_evidence"])


@pytest.mark.asyncio
async def test_get_asset_timeline_returns_newest_analysis_first(client, seeded_asset_context):
    response = await client.get(
        f"/api/assets/{seeded_asset_context['asset_id']}/timeline?limit=2"
    )

    assert response.status_code == 200
    payload = response.json()

    assert [entry["analysis_id"] for entry in payload["analyses"]] == [
        seeded_asset_context["analysis_id"],
        seeded_asset_context["prior_analysis_id"],
    ]
    assert payload["analyses"][0]["recommended_action"] == "continue_operations"
    assert payload["analyses"][1]["recommended_action"] == "monitor"


@pytest.mark.asyncio
async def test_get_asset_detail_classifies_runtime_public_source_types(client, session_factory):
    async with session_factory() as session:
        org = Organization(name="Asset API Public Domain Org")
        session.add(org)
        await session.commit()
        await session.refresh(org)

        asset_repo = AssetRepository(session)
        evidence_repo = EvidenceRepository(session)
        asset = await asset_repo.resolve_or_create(
            org_id=org.id,
            norad_id="70001",
            asset_type="satellite",
            name="PublicDomainSat",
        )

        for source_type, provider in (
            ("satnogs", "SatNOGS"),
            ("noaa_swpc", "NOAA SWPC"),
            ("ordem", "NASA ORDEM 4.0"),
        ):
            await evidence_repo.create_record(
                org_id=org.id,
                asset_id=asset.id,
                source_type=source_type,
                evidence_role="runtime",
                provider=provider,
                payload_json={"source_type": source_type},
            )

    response = await client.get(f"/api/assets/{asset.id}")

    assert response.status_code == 200
    payload = response.json()

    assert payload["evidence_summary"]["total_records"] == 3
    assert payload["evidence_summary"]["counts_by_domain"]["public"] == 3
    items_by_source = {item["source_type"]: item for item in payload["recent_evidence"]}
    assert items_by_source["satnogs"]["source_domain"] == "public"
    assert items_by_source["noaa_swpc"]["source_domain"] == "public"
    assert items_by_source["ordem"]["source_domain"] == "public"


@pytest.mark.asyncio
async def test_get_asset_detail_counts_partner_evidence_without_double_counting(
    client, session_factory
):
    async with session_factory() as session:
        org = Organization(name="Asset API Partner Domain Org")
        session.add(org)
        await session.commit()
        await session.refresh(org)

        asset_repo = AssetRepository(session)
        evidence_repo = EvidenceRepository(session)
        asset = await asset_repo.resolve_or_create(
            org_id=org.id,
            norad_id="70002",
            asset_type="satellite",
            name="PartnerDomainSat",
        )

        await evidence_repo.create_record(
            org_id=org.id,
            asset_id=asset.id,
            source_type="celestrak",
            evidence_role="runtime",
            provider="CelesTrak",
            payload_json={"variant": "public"},
        )
        await evidence_repo.create_record(
            org_id=org.id,
            asset_id=asset.id,
            source_type="celestrak",
            evidence_role="runtime",
            provider="partner:Acme Space",
            payload_json={"variant": "partner"},
        )

    response = await client.get(f"/api/assets/{asset.id}")

    assert response.status_code == 200
    payload = response.json()

    assert payload["evidence_summary"]["total_records"] == 2
    assert payload["evidence_summary"]["counts_by_domain"]["public"] == 1
    assert payload["evidence_summary"]["counts_by_domain"]["partner"] == 1
    assert sum(payload["evidence_summary"]["counts_by_domain"].values()) == 2
    partner_items = [
        item for item in payload["recent_evidence"] if item["provider"] == "partner:Acme Space"
    ]
    assert len(partner_items) == 1
    assert partner_items[0]["source_domain"] == "partner"
