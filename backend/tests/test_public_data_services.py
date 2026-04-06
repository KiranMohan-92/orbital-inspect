import os
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("GEMINI_API_KEY", "test-dummy-key")

from db.base import Base
from db.models import Analysis, Asset, Organization
from models.evidence import EvidenceBundle, EvidenceItem, EvidenceSource
from services.evidence_ingest_service import persist_evidence_bundle
from services.satnogs_service import fetch_recent_observations, summarize_observations
from services.ucs_service import lookup_by_norad_id, parse_ucs_text


class _FakeResponse:
    def __init__(self, payload, status_code: int = 200, text_value: str | None = None):
        self._payload = payload
        self.status_code = status_code
        self.text = text_value if text_value is not None else ""

    def json(self):
        return self._payload


class _FakeAsyncClient:
    def __init__(self, payloads):
        self.payloads = payloads

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, params=None):
        payload = self.payloads[url]
        if isinstance(payload, str):
            return _FakeResponse([], text_value=payload)
        return _FakeResponse(payload)


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


def test_parse_ucs_text_supports_tab_delimited_public_database():
    payload = (
        "NORAD Number\tName of Satellite, Alternate Names\tCountry of Operator/Owner\tPurpose\tClass of Orbit\tContractor\n"
        "25544\tISS (ZARYA)\tMultinational\tCivil\tLEO\tBoeing\n"
    )
    rows = parse_ucs_text(payload)

    assert len(rows) == 1
    assert rows[0]["NORAD Number"] == "25544"
    assert rows[0]["Contractor"] == "Boeing"


@pytest.mark.asyncio
async def test_lookup_ucs_by_norad_id_normalizes_public_reference_profile(monkeypatch):
    payload = (
        "NORAD Number\tCOSPAR Number\tName of Satellite, Alternate Names\tCountry of Operator/Owner\tPurpose\tClass of Orbit\tType of Orbit\tPower (watts)\tContractor\tBus\n"
        "25544\t1998-067A\tISS (ZARYA)\tMultinational\tCivil\tLEO\tNon-Polar Inclined\t120000\tBoeing\tZarya\n"
    )
    monkeypatch.setattr(
        "services.ucs_service.httpx.AsyncClient",
        lambda timeout, follow_redirects=True: _FakeAsyncClient({"https://example.test/ucs.txt": payload}),
    )

    record = await lookup_by_norad_id("25544", source_url="https://example.test/ucs.txt")

    assert record["norad_id"] == "25544"
    assert record["name"] == "ISS (ZARYA)"
    assert record["manufacturer"] == "Boeing"
    assert record["cospar_id"] == "1998-067A"
    assert record["manufacturer_designation"] == "Zarya"
    assert record["power_w"] == pytest.approx(120000.0)


@pytest.mark.asyncio
async def test_satnogs_fetch_and_summary(monkeypatch):
    payloads = {
        "https://network.satnogs.org/api/observations/": [
            {
                "id": 1,
                "norad_cat_id": 25544,
                "start": "2026-04-05T12:00:00Z",
                "end": "2026-04-05T12:10:00Z",
                "station_name": "Warsaw GS",
                "vetted_status": "good",
                "max_altitude": 61,
                "archive_url": "https://example.test/archive/1",
                "transmitter_mode": "FM",
                "transmitter_description": "Voice",
                "transmitter_downlink_low": 145800000,
            },
            {
                "id": 2,
                "norad_cat_id": 25544,
                "start": "2026-04-04T12:00:00Z",
                "end": "2026-04-04T12:10:00Z",
                "station_name": "Berlin GS",
                "vetted_status": "good",
                "max_altitude": 43,
                "archive_url": None,
                "transmitter_mode": "FM",
                "transmitter_description": "Voice",
                "transmitter_downlink_low": 145800000,
            },
        ]
    }
    monkeypatch.setattr(
        "services.satnogs_service.httpx.AsyncClient",
        lambda timeout: _FakeAsyncClient(payloads),
    )

    observations = await fetch_recent_observations("25544", limit=5)
    summary = summarize_observations(observations)

    assert len(observations) == 2
    assert observations[0]["station_name"] == "Warsaw GS"
    assert summary["distinct_stations"] == 2
    assert summary["observation_count"] == 2
    assert summary["transmitter_modes"] == ["FM"]


@pytest.mark.asyncio
async def test_persist_evidence_bundle_creates_reusable_records_and_links(session: AsyncSession):
    org = Organization(name="Evidence Org")
    asset = Asset(org_id=None, norad_id="25544", name="ISS", asset_type="satellite")
    analysis = Analysis(org_id=None, asset_type="satellite", norad_id="25544", status="queued")
    session.add_all([org, asset, analysis])
    await session.commit()
    await session.refresh(org)
    asset.org_id = org.id
    analysis.org_id = org.id
    analysis.asset_id = asset.id
    await session.commit()

    bundle = EvidenceBundle(satellite_id="25544", satellite_name="ISS")
    bundle.add_item(EvidenceItem(
        source=EvidenceSource.REFERENCE_PROFILE,
        data_type="application/json",
        timestamp=datetime.now(timezone.utc).isoformat(),
        description="Public reference profile",
        confidence=0.75,
        payload={"operator_name": "Multinational"},
        metadata={
            "provider": "UCS",
            "external_ref": "ucs:25544",
            "source_url": "https://www.ucs.org/resources/satellite-database",
            "tags": ["baseline", "public"],
        },
    ))
    bundle.add_item(EvidenceItem(
        source=EvidenceSource.RF_ACTIVITY,
        data_type="application/json",
        timestamp="2026-04-05T12:00:00Z",
        description="SatNOGS observation activity",
        confidence=0.6,
        payload={"observation_count": 2},
        metadata={
            "provider": "SatNOGS",
            "external_ref": "satnogs:25544:2026-04-05T12:00:00Z",
            "source_url": "https://network.satnogs.org/",
            "tags": ["rf_activity", "public"],
        },
    ))

    linked = await persist_evidence_bundle(
        session,
        analysis_id=analysis.id,
        org_id=org.id,
        asset_id=asset.id,
        subsystem_id=None,
        bundle=bundle,
    )
    linked_again = await persist_evidence_bundle(
        session,
        analysis_id=analysis.id,
        org_id=org.id,
        asset_id=asset.id,
        subsystem_id=None,
        bundle=bundle,
    )

    evidence_count = (await session.execute(text("SELECT COUNT(*) FROM evidence_records"))).scalar_one()
    link_count = (await session.execute(text("SELECT COUNT(*) FROM analysis_evidence_links"))).scalar_one()

    assert linked == 2
    assert linked_again == 2
    assert evidence_count == 2
    assert link_count == 2
