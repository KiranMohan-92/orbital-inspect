"""Fail CI when blocking verification gates lack review artifacts."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GATES_FILE = REPO_ROOT / ".agents" / "verification-gates.yaml"
REVIEWS_DIR = REPO_ROOT / ".agents" / "reviews"

GATE_PATTERNS: dict[str, tuple[str, ...]] = {
    "security_change": (
        "backend/auth/",
        "backend/api/webhooks.py",
        "backend/services/webhook_",
        "backend/services/secret_service.py",
        "backend/services/storage_service.py",
        "backend/main.py",
        "ops/helm/",
    ),
    "llm_output_handling": (
        "backend/services/gemini_service.py",
        "backend/agents/",
        "backend/prompts/",
    ),
    "schema_migration": (
        "backend/alembic/",
        "backend/db/models.py",
    ),
    "insurance_logic": (
        "backend/models/satellite.py",
        "backend/models/provenance.py",
        "backend/agents/insurance_risk_agent.py",
        "backend/prompts/insurance_risk_prompt.txt",
        "backend/services/assessment_mode_service.py",
        "backend/services/decision_policy_service.py",
        "backend/services/governance_service.py",
        "backend/services/sensitivity_service.py",
    ),
    "report_mode_authority": (
        "backend/services/assessment_mode_service.py",
        "backend/main.py",
        "backend/api/reports.py",
        "backend/templates/report.html",
        "frontend/src/components/analysis/IntelligenceReport.tsx",
        "frontend/src/components/analysis/InsuranceRiskCard.tsx",
    ),
    "new_agent": (
        "backend/agents/",
    ),
}

BLOCKING_GATES = {"security_change", "llm_output_handling", "insurance_logic", "report_mode_authority", "new_agent"}


def _run_git(args: list[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True, stderr=subprocess.DEVNULL)


def _changed_files(base: str | None) -> list[str]:
    candidates = []
    if base:
        candidates.append([f"{base}...HEAD"])
        candidates.append([base, "HEAD"])
    candidates.append(["HEAD~1", "HEAD"])
    for candidate in candidates:
        try:
            return [
                line.strip().replace("\\", "/")
                for line in _run_git(["diff", "--name-only", *candidate]).splitlines()
                if line.strip()
            ]
        except Exception:
            continue
    return []


def _ci_blocking_enabled() -> bool:
    try:
        return 'mode: "ci-blocking"' in GATES_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        return False


def _triggered_gates(changed: list[str]) -> set[str]:
    triggered: set[str] = set()
    for gate, prefixes in GATE_PATTERNS.items():
        if any(path.startswith(prefix) for path in changed for prefix in prefixes):
            triggered.add(gate)
    return triggered & BLOCKING_GATES


def _review_artifact_ok(gate: str) -> bool:
    artifact = REVIEWS_DIR / f"{gate}.md"
    if not artifact.exists():
        return False
    text = artifact.read_text(encoding="utf-8").lower()
    return "status: approved" in text and "reviewer:" in text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=None)
    args = parser.parse_args()

    if not _ci_blocking_enabled():
        print("verification gates are advisory; skipping")
        return 0

    changed = _changed_files(args.base)
    triggered = _triggered_gates(changed)
    missing = sorted(gate for gate in triggered if not _review_artifact_ok(gate))
    if missing:
        print("Missing blocking verification review artifacts:")
        for gate in missing:
            print(f"  - .agents/reviews/{gate}.md")
        return 1

    print(f"verification gates passed for {len(changed)} changed files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
