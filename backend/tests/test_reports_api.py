"""
Tests for the Reports API (Rec #11 — Human Review Workflow).

Uses in-memory mocking to avoid database dependency.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from api.reports import router as reports_router


@pytest.fixture
def app():
    """Minimal FastAPI app with reports router mounted."""
    _app = FastAPI()
    _app.include_router(reports_router)
    return _app


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


def _make_report(report_id="r1", analysis_id="a1", status="DRAFT"):
    """Build a mock Report ORM object."""
    r = MagicMock()
    r.id = report_id
    r.analysis_id = analysis_id
    r.status = status
    r.version = 1
    r.full_report_json = {}
    r.submitted_by = None
    r.submitted_at = None
    r.approved_by = None
    r.approved_at = None
    r.reviewer_comments = []
    r.created_at = None
    return r


def _make_analysis(analysis_id="a1", status="completed"):
    a = MagicMock()
    a.id = analysis_id
    a.status = status
    a.classification_result = {}
    a.vision_result = {}
    a.environment_result = {}
    a.failure_mode_result = {}
    a.insurance_risk_result = {}
    a.evidence_gaps = []
    a.report_completeness = "COMPLETE"
    return a


class TestCreateReport:
    def test_create_report_success(self, client):
        analysis = _make_analysis()
        mock_report = _make_report()

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        analysis_repo = AsyncMock()
        analysis_repo.get = AsyncMock(return_value=analysis)

        report_repo = AsyncMock()
        report_repo.get_by_analysis = AsyncMock(return_value=None)
        report_repo.create = AsyncMock(return_value=mock_report)

        with patch("db.base.async_session_factory", return_value=mock_session), \
             patch("db.repository.AnalysisRepository", return_value=analysis_repo), \
             patch("db.repository.ReportRepository", return_value=report_repo):
            resp = client.post("/api/reports/a1/create")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "r1"
        assert data["status"] == "DRAFT"

    def test_create_report_analysis_not_found(self, client):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        analysis_repo = AsyncMock()
        analysis_repo.get = AsyncMock(return_value=None)

        with patch("db.base.async_session_factory", return_value=mock_session), \
             patch("db.repository.AnalysisRepository", return_value=analysis_repo), \
             patch("db.repository.ReportRepository", return_value=AsyncMock()):
            resp = client.post("/api/reports/missing/create")

        assert resp.status_code == 404

    def test_create_report_analysis_not_completed(self, client):
        analysis = _make_analysis(status="running")
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        analysis_repo = AsyncMock()
        analysis_repo.get = AsyncMock(return_value=analysis)

        with patch("db.base.async_session_factory", return_value=mock_session), \
             patch("db.repository.AnalysisRepository", return_value=analysis_repo), \
             patch("db.repository.ReportRepository", return_value=AsyncMock()):
            resp = client.post("/api/reports/a1/create")

        assert resp.status_code == 400
        assert "not yet completed" in resp.json()["detail"]

    def test_create_report_already_exists(self, client):
        analysis = _make_analysis()
        existing = _make_report(status="PENDING_REVIEW")
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        analysis_repo = AsyncMock()
        analysis_repo.get = AsyncMock(return_value=analysis)

        report_repo = AsyncMock()
        report_repo.get_by_analysis = AsyncMock(return_value=existing)

        with patch("db.base.async_session_factory", return_value=mock_session), \
             patch("db.repository.AnalysisRepository", return_value=analysis_repo), \
             patch("db.repository.ReportRepository", return_value=report_repo):
            resp = client.post("/api/reports/a1/create")

        assert resp.status_code == 200
        assert resp.json()["message"] == "Report already exists"


class TestSubmitReview:
    def test_submit_draft_report(self, client):
        report = _make_report(status="DRAFT")
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        repo = AsyncMock()
        repo.get = AsyncMock(return_value=report)
        repo.update_status = AsyncMock()

        with patch("db.base.async_session_factory", return_value=mock_session), \
             patch("db.repository.ReportRepository", return_value=repo):
            resp = client.post("/api/reports/r1/submit-review", json={"notes": "ready"})

        assert resp.status_code == 200
        assert resp.json()["status"] == "PENDING_REVIEW"

    def test_submit_non_draft_fails(self, client):
        report = _make_report(status="APPROVED")
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        repo = AsyncMock()
        repo.get = AsyncMock(return_value=report)

        with patch("db.base.async_session_factory", return_value=mock_session), \
             patch("db.repository.ReportRepository", return_value=repo):
            resp = client.post("/api/reports/r1/submit-review", json={"notes": ""})

        assert resp.status_code == 400
        assert "Cannot submit" in resp.json()["detail"]

    def test_submit_report_not_found(self, client):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        repo = AsyncMock()
        repo.get = AsyncMock(return_value=None)

        with patch("db.base.async_session_factory", return_value=mock_session), \
             patch("db.repository.ReportRepository", return_value=repo):
            resp = client.post("/api/reports/missing/submit-review", json={"notes": ""})

        assert resp.status_code == 404


class TestApproveReport:
    def test_approve_pending_review(self, client):
        report = _make_report(status="PENDING_REVIEW")
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        repo = AsyncMock()
        repo.get = AsyncMock(return_value=report)
        repo.update_status = AsyncMock()

        with patch("db.base.async_session_factory", return_value=mock_session), \
             patch("db.repository.ReportRepository", return_value=repo):
            resp = client.post("/api/reports/r1/approve", json={"comments": "LGTM"})

        assert resp.status_code == 200
        assert resp.json()["status"] == "APPROVED"

    def test_approve_wrong_status_fails(self, client):
        report = _make_report(status="DRAFT")
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        repo = AsyncMock()
        repo.get = AsyncMock(return_value=report)

        with patch("db.base.async_session_factory", return_value=mock_session), \
             patch("db.repository.ReportRepository", return_value=repo):
            resp = client.post("/api/reports/r1/approve", json={"comments": ""})

        assert resp.status_code == 400
        assert "Cannot approve" in resp.json()["detail"]


class TestRejectReport:
    def test_reject_pending_review(self, client):
        report = _make_report(status="PENDING_REVIEW")
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        repo = AsyncMock()
        repo.get = AsyncMock(return_value=report)
        repo.update_status = AsyncMock()

        with patch("db.base.async_session_factory", return_value=mock_session), \
             patch("db.repository.ReportRepository", return_value=repo):
            resp = client.post("/api/reports/r1/reject", json={"reason": "Needs more detail"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "DRAFT"
        assert data["reason"] == "Needs more detail"

    def test_reject_wrong_status_fails(self, client):
        report = _make_report(status="DRAFT")
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        repo = AsyncMock()
        repo.get = AsyncMock(return_value=report)

        with patch("db.base.async_session_factory", return_value=mock_session), \
             patch("db.repository.ReportRepository", return_value=repo):
            resp = client.post("/api/reports/r1/reject", json={"reason": "bad"})

        assert resp.status_code == 400

    def test_reject_requires_reason(self, client):
        resp = client.post("/api/reports/r1/reject", json={})
        assert resp.status_code == 422


class TestGetReport:
    def test_get_existing_report(self, client):
        report = _make_report(status="APPROVED")
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        repo = AsyncMock()
        repo.get = AsyncMock(return_value=report)

        with patch("db.base.async_session_factory", return_value=mock_session), \
             patch("db.repository.ReportRepository", return_value=repo):
            resp = client.get("/api/reports/r1")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "r1"
        assert data["status"] == "APPROVED"

    def test_get_missing_report(self, client):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        repo = AsyncMock()
        repo.get = AsyncMock(return_value=None)

        with patch("db.base.async_session_factory", return_value=mock_session), \
             patch("db.repository.ReportRepository", return_value=repo):
            resp = client.get("/api/reports/missing")

        assert resp.status_code == 404
