"""ITAR/CUI classification marking service.

Assigns data classification levels to evidence, analyses, and reports
based on data source and organizational policy. Classification propagates
through the evidence chain — the highest classification wins.
"""

import logging
from typing import Any

log = logging.getLogger(__name__)

# Classification levels in ascending order of sensitivity
CLASSIFICATION_LEVELS = ["UNCLASSIFIED", "CUI", "ITAR_CONTROLLED", "PROPRIETARY"]

# Default classification by data source type
_SOURCE_CLASSIFICATION: dict[str, str] = {
    # Public sources — freely available data
    "celestrak": "UNCLASSIFIED",
    "tle_history": "UNCLASSIFIED",
    "conjunction_risk": "UNCLASSIFIED",
    "space_weather": "UNCLASSIFIED",
    "debris_environment": "UNCLASSIFIED",
    "reference_profile": "UNCLASSIFIED",
    "rf_activity": "UNCLASSIFIED",
    "satnogs": "UNCLASSIFIED",
    "noaa_swpc": "UNCLASSIFIED",
    "ordem": "UNCLASSIFIED",
    # Operator-supplied — proprietary by default
    "imagery": "PROPRIETARY",
    "operator_telemetry": "PROPRIETARY",
    "telemetry": "PROPRIETARY",
    "operator_notes": "PROPRIETARY",
    "maintenance_records": "PROPRIETARY",
    # Internal
    "internal_prior_analysis": "CUI",
    "prior_analysis": "CUI",
}


def classify_source(source_type: str, provider: str | None = None) -> str:
    """Determine classification for a data source.

    Returns the classification level for the given source type.
    Partner data defaults to CUI unless explicitly marked.
    """
    source_lower = source_type.lower() if source_type else ""
    provider_lower = (provider or "").lower()

    # Partner data defaults to CUI
    if provider_lower.startswith("partner:"):
        return "CUI"

    return _SOURCE_CLASSIFICATION.get(source_lower, "CUI")


def classification_level(marking: str) -> int:
    """Return numeric level for comparison (higher = more restricted)."""
    try:
        return CLASSIFICATION_LEVELS.index(marking)
    except ValueError:
        return len(CLASSIFICATION_LEVELS) - 1  # Default to most restricted


def highest_classification(*markings: str) -> str:
    """Return the highest (most restricted) classification from a set."""
    if not markings:
        return "UNCLASSIFIED"
    return max(markings, key=classification_level)


def propagate_classification(evidence_markings: list[str]) -> str:
    """Propagate classification through evidence chain.

    An analysis inherits the highest classification of its linked evidence.
    A report inherits the classification of its analysis.
    """
    if not evidence_markings:
        return "UNCLASSIFIED"
    return highest_classification(*evidence_markings)


def classification_banner(marking: str) -> str:
    """Generate a human-readable classification banner for PDF reports."""
    banners = {
        "UNCLASSIFIED": "UNCLASSIFIED",
        "CUI": "CUI // CONTROLLED UNCLASSIFIED INFORMATION",
        "ITAR_CONTROLLED": "ITAR CONTROLLED // WARNING: This document contains technical data subject to ITAR (22 CFR Parts 120-130)",
        "PROPRIETARY": "PROPRIETARY // COMPANY CONFIDENTIAL",
    }
    return banners.get(marking, f"CLASSIFICATION: {marking}")


def classification_header_value(marking: str) -> str:
    """Return the value for the X-Classification-Marking HTTP header."""
    return marking
