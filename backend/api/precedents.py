"""
Precedent knowledge base API — searchable satellite failure/insurance incidents.
"""

import json
import logging
from pathlib import Path
from fastapi import APIRouter, Query

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/precedents", tags=["precedents"])

_DATA_PATH = Path(__file__).parent.parent / "data" / "precedents.json"
_precedents: list[dict] = []


def _load_precedents():
    global _precedents
    if not _precedents and _DATA_PATH.exists():
        _precedents = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
        log.info("Loaded %d precedents", len(_precedents))


@router.get("")
async def search_precedents(
    failure_mode: str = Query(default="", description="Filter by failure mode"),
    orbital_regime: str = Query(default="", description="Filter by orbital regime (LEO, GEO, MEO)"),
    tag: str = Query(default="", description="Filter by tag"),
    q: str = Query(default="", description="Full-text search across all fields"),
    limit: int = Query(default=25, le=100),
):
    """Search the precedent knowledge base."""
    _load_precedents()

    results = _precedents

    if failure_mode:
        results = [p for p in results if failure_mode.lower() in p.get("failure_mode", "").lower()]

    if orbital_regime:
        results = [p for p in results if orbital_regime.upper() in p.get("orbital_regime", "").upper()]

    if tag:
        results = [p for p in results if tag.lower() in [t.lower() for t in p.get("tags", [])]]

    if q:
        q_lower = q.lower()
        results = [
            p for p in results
            if q_lower in json.dumps(p).lower()
        ]

    return {
        "results": results[:limit],
        "total": len(results),
        "limit": limit,
    }


@router.get("/tags")
async def list_tags():
    """List all available tags with counts."""
    _load_precedents()
    tag_counts: dict[str, int] = {}
    for p in _precedents:
        for tag in p.get("tags", []):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    return {"tags": dict(sorted(tag_counts.items(), key=lambda x: -x[1]))}


@router.get("/{precedent_id}")
async def get_precedent(precedent_id: int):
    """Get a specific precedent by ID."""
    _load_precedents()
    for p in _precedents:
        if p.get("id") == precedent_id:
            return p
    return {"error": "Precedent not found"}
