"""
Tests for the Reports API (Rec #11 — Human Review Workflow).

Uses direct route calls with mocked repositories to avoid database and ASGI
transport issues in the test environment.
"""

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from unittest.mock import AsyncMock, MagicMock, patch

from api.reports import (
    ApproveRequest,
    RejectRequest,
    SubmitReviewRequest,
    approve_report,
    create_report,
    get_report,
    reject_report,
    submit_for_review,
)
from auth.dependencies import CurrentUser


class _MockSessionContext:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _make_mock_session():
    return _MockSessionContext()


def _make_report(report_id="r1", analysis_id="a1", status="DRAFT"):
    """Build a mock Report ORM object."""
    report = MagicMock()
    report.id = report_id
    report.analysis_id = analysis_id
    report.status = status
    report.version = 1
    report.full_report_json = {}
    report.submitted_by = None
    report.submitted_at = None
    report.approved_by = None
    report.approved_at = None
    report.reviewer_comments = []
    report.created_at = None
    return report


def _make_analysis(analysis_id="a1", status="completed"):
    analysis = MagicMock()
    analysis.id = analysis_id
    analysis.status = status
    analysis.classification_result = {}
    analysis.vision_result = {}
    analysis.environment_result = {}
    analysis.failure_mode_result = {}
    analysis.insurance_risk_result = {}
    analysis.evidence_gaps = []
    analysis.report_completeness = "COMPLETE"
    return analysis


@pytest.mark.asyncio
async def test_create_report_success():
    analysis = _make_analysis()
    mock_report = _make_report()
    mock_session = _make_mock_session()
    user = CurrentUser(user_id="u1", org_id="org-1", role="analyst")

    analysis_repo = AsyncMock()
    analysis_repo.get = AsyncMock(return_value=analysis)

    report_repo = AsyncMock()
    report_repo.get_by_analysis = AsyncMock(return_value=None)
    report_repo.create = AsyncMock(return_value=mock_report)

    with patch("db.base.async_session_factory", return_value=mock_session), \
         patch("db.repository.AnalysisRepository", return_value=analysis_repo), \
         patch("db.repository.ReportRepository", return_value=report_repo):
        data = await create_report("a1", user=user)

    assert data["id"] == "r1"
    assert data["status"] == "DRAFT"
    analysis_repo.get.assert_awaited_once_with("a1", org_id="org-1")
    report_repo.get_by_analysis.assert_awaited_once_with("a1", org_id="org-1")


@pytest.mark.asyncio
async def test_create_report_analysis_not_found():
    mock_session = _make_mock_session()
    analysis_repo = AsyncMock()
    analysis_repo.get = AsyncMock(return_value=None)

    with patch("db.base.async_session_factory", return_value=mock_session), \
         patch("db.repository.AnalysisRepository", return_value=analysis_repo), \
         patch("db.repository.ReportRepository", return_value=AsyncMock()):
        with pytest.raises(HTTPException) as exc:
            await create_report("missing", user=None)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_create_report_analysis_not_completed():
    analysis = _make_analysis(status="running")
    mock_session = _make_mock_session()
    analysis_repo = AsyncMock()
    analysis_repo.get = AsyncMock(return_value=analysis)

    with patch("db.base.async_session_factory", return_value=mock_session), \
         patch("db.repository.AnalysisRepository", return_value=analysis_repo), \
         patch("db.repository.ReportRepository", return_value=AsyncMock()):
        with pytest.raises(HTTPException) as exc:
            await create_report("a1", user=None)

    assert exc.value.status_code == 400
    assert "not yet completed" in exc.value.detail


@pytest.mark.asyncio
async def test_create_report_already_exists():
    analysis = _make_analysis()
    existing = _make_report(status="PENDING_REVIEW")
    mock_session = _make_mock_session()

    analysis_repo = AsyncMock()
    analysis_repo.get = AsyncMock(return_value=analysis)

    report_repo = AsyncMock()
    report_repo.get_by_analysis = AsyncMock(return_value=existing)

    with patch("db.base.async_session_factory", return_value=mock_session), \
         patch("db.repository.AnalysisRepository", return_value=analysis_repo), \
         patch("db.repository.ReportRepository", return_value=report_repo):
        data = await create_report("a1", user=None)

    assert data["message"] == "Report already exists"


@pytest.mark.asyncio
async def test_submit_draft_report():
    report = _make_report(status="DRAFT")
    mock_session = _make_mock_session()
    user = CurrentUser(user_id="u1", org_id="org-1", role="analyst")

    repo = AsyncMock()
    repo.get = AsyncMock(return_value=report)
    repo.update_status = AsyncMock()

    with patch("db.base.async_session_factory", return_value=mock_session), \
         patch("db.repository.ReportRepository", return_value=repo):
        data = await submit_for_review("r1", SubmitReviewRequest(notes="ready"), user=user)

    assert data["status"] == "PENDING_REVIEW"
    repo.get.assert_awaited_once_with("r1", org_id="org-1")


@pytest.mark.asyncio
async def test_submit_non_draft_fails():
    report = _make_report(status="APPROVED")
    mock_session = _make_mock_session()

    repo = AsyncMock()
    repo.get = AsyncMock(return_value=report)

    with patch("db.base.async_session_factory", return_value=mock_session), \
         patch("db.repository.ReportRepository", return_value=repo):
        with pytest.raises(HTTPException) as exc:
            await submit_for_review("r1", SubmitReviewRequest(notes=""), user=None)

    assert exc.value.status_code == 400
    assert "Cannot submit" in exc.value.detail


@pytest.mark.asyncio
async def test_submit_report_not_found():
    mock_session = _make_mock_session()
    repo = AsyncMock()
    repo.get = AsyncMock(return_value=None)

    with patch("db.base.async_session_factory", return_value=mock_session), \
         patch("db.repository.ReportRepository", return_value=repo):
        with pytest.raises(HTTPException) as exc:
            await submit_for_review("missing", SubmitReviewRequest(notes=""), user=None)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_approve_pending_review():
    report = _make_report(status="PENDING_REVIEW")
    mock_session = _make_mock_session()
    user = CurrentUser(user_id="admin-1", org_id="org-1", role="admin")

    repo = AsyncMock()
    repo.get = AsyncMock(return_value=report)
    repo.update_status = AsyncMock()

    with patch("db.base.async_session_factory", return_value=mock_session), \
         patch("db.repository.ReportRepository", return_value=repo):
        data = await approve_report("r1", ApproveRequest(comments="LGTM"), user=user)

    assert data["status"] == "APPROVED"
    repo.get.assert_awaited_once_with("r1", org_id="org-1")


@pytest.mark.asyncio
async def test_approve_wrong_status_fails():
    report = _make_report(status="DRAFT")
    mock_session = _make_mock_session()

    repo = AsyncMock()
    repo.get = AsyncMock(return_value=report)

    with patch("db.base.async_session_factory", return_value=mock_session), \
         patch("db.repository.ReportRepository", return_value=repo):
        with pytest.raises(HTTPException) as exc:
            await approve_report("r1", ApproveRequest(comments=""), user=None)

    assert exc.value.status_code == 400
    assert "Cannot approve" in exc.value.detail


@pytest.mark.asyncio
async def test_reject_pending_review():
    report = _make_report(status="PENDING_REVIEW")
    mock_session = _make_mock_session()
    user = CurrentUser(user_id="admin-1", org_id="org-1", role="admin")

    repo = AsyncMock()
    repo.get = AsyncMock(return_value=report)
    repo.update_status = AsyncMock()

    with patch("db.base.async_session_factory", return_value=mock_session), \
         patch("db.repository.ReportRepository", return_value=repo):
        data = await reject_report("r1", RejectRequest(reason="Needs more detail"), user=user)

    assert data["status"] == "DRAFT"
    assert data["reason"] == "Needs more detail"
    repo.get.assert_awaited_once_with("r1", org_id="org-1")


@pytest.mark.asyncio
async def test_reject_wrong_status_fails():
    report = _make_report(status="DRAFT")
    mock_session = _make_mock_session()

    repo = AsyncMock()
    repo.get = AsyncMock(return_value=report)

    with patch("db.base.async_session_factory", return_value=mock_session), \
         patch("db.repository.ReportRepository", return_value=repo):
        with pytest.raises(HTTPException) as exc:
            await reject_report("r1", RejectRequest(reason="bad"), user=None)

    assert exc.value.status_code == 400


def test_reject_requires_reason():
    with pytest.raises(ValidationError):
        RejectRequest()


@pytest.mark.asyncio
async def test_get_existing_report():
    report = _make_report(status="APPROVED")
    mock_session = _make_mock_session()
    user = CurrentUser(user_id="viewer-1", org_id="org-1", role="viewer")

    repo = AsyncMock()
    repo.get = AsyncMock(return_value=report)

    with patch("db.base.async_session_factory", return_value=mock_session), \
         patch("db.repository.ReportRepository", return_value=repo):
        data = await get_report("r1", user=user)

    assert data["id"] == "r1"
    assert data["status"] == "APPROVED"
    repo.get.assert_awaited_once_with("r1", org_id="org-1")


@pytest.mark.asyncio
async def test_get_missing_report():
    mock_session = _make_mock_session()
    repo = AsyncMock()
    repo.get = AsyncMock(return_value=None)

    with patch("db.base.async_session_factory", return_value=mock_session), \
         patch("db.repository.ReportRepository", return_value=repo):
        with pytest.raises(HTTPException) as exc:
            await get_report("missing", user=None)

    assert exc.value.status_code == 404
