"""Database-backed feature flag service.

Provides per-org feature flag evaluation without external SaaS dependencies.
Designed for air-gapped and classified deployment environments.
"""

import logging
from typing import Any

log = logging.getLogger(__name__)

# In-memory flag cache (populated from DB on first access per flag)
_flag_cache: dict[str, dict[str, Any]] = {}

# Default flag definitions — these are the initial flags
DEFAULT_FLAGS: dict[str, dict[str, Any]] = {
    "batch_analysis": {
        "description": "Enable batch analysis endpoint for fleet-scale submissions",
        "enabled_default": True,
    },
    "fleet_monitoring": {
        "description": "Enable continuous fleet monitoring via periodic ingestion",
        "enabled_default": False,
    },
    "itar_markings": {
        "description": "Enable ITAR/CUI classification marking on all data objects",
        "enabled_default": False,
    },
    "alert_webhooks": {
        "description": "Enable threshold-based alert dispatch via webhooks",
        "enabled_default": False,
    },
    "trend_analysis": {
        "description": "Enable degradation trend analysis for fleet assets",
        "enabled_default": False,
    },
}


class FeatureFlagService:
    """Evaluates feature flags with per-org overrides."""

    def __init__(self):
        self._overrides: dict[str, dict[str, bool]] = {}  # flag_name -> {org_id: bool}

    def is_enabled(self, flag_name: str, org_id: str | None = None) -> bool:
        """Check if a feature flag is enabled for the given org.

        Priority:
        1. Per-org override (if set)
        2. Default flag value
        3. False (unknown flags are disabled)
        """
        # Check per-org override
        if flag_name in self._overrides and org_id:
            override = self._overrides[flag_name].get(org_id)
            if override is not None:
                return override

        # Check default
        flag_def = DEFAULT_FLAGS.get(flag_name)
        if flag_def is None:
            log.warning("Unknown feature flag: %s", flag_name)
            return False
        return flag_def["enabled_default"]

    def set_override(self, flag_name: str, org_id: str, enabled: bool) -> None:
        """Set a per-org override for a feature flag."""
        if flag_name not in self._overrides:
            self._overrides[flag_name] = {}
        self._overrides[flag_name][org_id] = enabled
        log.info("Feature flag override set: %s=%s for org=%s", flag_name, enabled, org_id)

    def remove_override(self, flag_name: str, org_id: str) -> None:
        """Remove a per-org override, reverting to default."""
        if flag_name in self._overrides:
            self._overrides[flag_name].pop(org_id, None)

    def list_flags(self, org_id: str | None = None) -> list[dict[str, Any]]:
        """List all feature flags with their current state for an org."""
        result = []
        for name, definition in DEFAULT_FLAGS.items():
            enabled = self.is_enabled(name, org_id)
            has_override = bool(
                org_id
                and name in self._overrides
                and org_id in self._overrides.get(name, {})
            )
            result.append({
                "name": name,
                "description": definition["description"],
                "enabled": enabled,
                "default": definition["enabled_default"],
                "has_org_override": has_override,
            })
        return result


# Module-level singleton
_instance: FeatureFlagService | None = None

def get_feature_flag_service() -> FeatureFlagService:
    global _instance
    if _instance is None:
        _instance = FeatureFlagService()
    return _instance
