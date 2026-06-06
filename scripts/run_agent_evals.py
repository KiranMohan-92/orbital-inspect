"""Run deterministic agent-evolution eval suites.

The runner is intentionally dependency-free so the guardrail suite can run in
fresh CI environments before backend/frontend dependencies are installed.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUITE = REPO_ROOT / ".agents" / "evals" / "orbital_inspect_guardrails.json"


class EvalError(Exception):
    """Raised when an eval suite or grader is invalid."""


@dataclass(frozen=True)
class GraderResult:
    passed: bool
    message: str
    details: dict[str, Any]


@dataclass(frozen=True)
class EvalResult:
    eval_id: str
    title: str
    category: str
    critical: bool
    passed: bool
    graders: list[GraderResult]
    duration_ms: int


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EvalError(f"{path}: invalid JSON: {exc}") from exc
    except FileNotFoundError as exc:
        raise EvalError(f"{path}: file not found") from exc


def _repo_path(raw_path: str | Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        resolved = path.resolve()
    else:
        resolved = (REPO_ROOT / path).resolve()
    try:
        resolved.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise EvalError(f"path escapes repository: {raw_path}") from exc
    return resolved


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EvalError(message)


def _validate_suite(suite: dict[str, Any], suite_path: Path) -> None:
    _require(isinstance(suite, dict), f"{suite_path}: suite must be an object")
    _require(suite.get("version") == 1, f"{suite_path}: version must be 1")
    _require(isinstance(suite.get("suite_id"), str) and suite["suite_id"], "suite_id is required")
    _require(isinstance(suite.get("name"), str) and suite["name"], "name is required")
    evals = suite.get("evals")
    _require(isinstance(evals, list) and evals, "evals must be a non-empty list")

    seen: set[str] = set()
    for index, eval_case in enumerate(evals):
        prefix = f"evals[{index}]"
        _require(isinstance(eval_case, dict), f"{prefix}: must be an object")
        eval_id = eval_case.get("id")
        _require(isinstance(eval_id, str) and eval_id, f"{prefix}.id is required")
        _require(eval_id not in seen, f"duplicate eval id: {eval_id}")
        seen.add(eval_id)
        _require(isinstance(eval_case.get("title"), str) and eval_case["title"], f"{eval_id}: title is required")
        _require(isinstance(eval_case.get("category"), str) and eval_case["category"], f"{eval_id}: category is required")
        _require(isinstance(eval_case.get("critical"), bool), f"{eval_id}: critical must be boolean")
        _require(
            isinstance(eval_case.get("rationale"), str) and eval_case["rationale"],
            f"{eval_id}: rationale is required",
        )
        graders = eval_case.get("graders")
        _require(isinstance(graders, list) and graders, f"{eval_id}: graders must be a non-empty list")
        for grader_index, grader in enumerate(graders):
            _validate_grader(eval_id, grader_index, grader)


def _validate_grader(eval_id: str, grader_index: int, grader: Any) -> None:
    prefix = f"{eval_id}.graders[{grader_index}]"
    _require(isinstance(grader, dict), f"{prefix}: must be an object")
    grader_type = grader.get("type")
    _require(isinstance(grader_type, str) and grader_type, f"{prefix}.type is required")

    if grader_type in {"file_contains", "file_not_contains", "file_regex", "json_field_equals"}:
        _require(isinstance(grader.get("path"), str) and grader["path"], f"{prefix}.path is required")
    if grader_type == "file_contains":
        _require(isinstance(grader.get("contains"), list) and grader["contains"], f"{prefix}.contains is required")
    elif grader_type == "file_not_contains":
        _require(isinstance(grader.get("forbidden"), list) and grader["forbidden"], f"{prefix}.forbidden is required")
    elif grader_type == "file_regex":
        _require(isinstance(grader.get("patterns"), list) and grader["patterns"], f"{prefix}.patterns is required")
    elif grader_type == "json_field_equals":
        _require(isinstance(grader.get("field"), str) and grader["field"], f"{prefix}.field is required")
        _require("equals" in grader, f"{prefix}.equals is required")
    elif grader_type == "command":
        _require(isinstance(grader.get("command"), list) and grader["command"], f"{prefix}.command is required")
        _require(all(isinstance(part, str) and part for part in grader["command"]), f"{prefix}.command parts must be strings")
    else:
        raise EvalError(f"{prefix}: unsupported grader type {grader_type!r}")


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise EvalError(f"{_rel(path)}: file not found") from exc


def _grade_file_contains(grader: dict[str, Any]) -> GraderResult:
    path = _repo_path(grader["path"])
    text = _read_text(path)
    missing = [needle for needle in grader["contains"] if needle not in text]
    return GraderResult(
        passed=not missing,
        message="all required strings present" if not missing else f"missing {len(missing)} required string(s)",
        details={"path": _rel(path), "missing": missing},
    )


def _grade_file_not_contains(grader: dict[str, Any]) -> GraderResult:
    path = _repo_path(grader["path"])
    text = _read_text(path)
    present = [needle for needle in grader["forbidden"] if needle in text]
    return GraderResult(
        passed=not present,
        message="no forbidden strings present" if not present else f"found {len(present)} forbidden string(s)",
        details={"path": _rel(path), "present": present},
    )


def _grade_file_regex(grader: dict[str, Any]) -> GraderResult:
    path = _repo_path(grader["path"])
    text = _read_text(path)
    missing: list[str] = []
    for pattern in grader["patterns"]:
        if not re.search(pattern, text, flags=re.MULTILINE):
            missing.append(pattern)
    return GraderResult(
        passed=not missing,
        message="all regex patterns matched" if not missing else f"missing {len(missing)} regex match(es)",
        details={"path": _rel(path), "missing": missing},
    )


def _field_value(data: Any, field: str) -> Any:
    current = data
    for part in field.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        raise EvalError(f"field {field!r} not found at {part!r}")
    return current


def _grade_json_field_equals(grader: dict[str, Any]) -> GraderResult:
    path = _repo_path(grader["path"])
    data = _load_json(path)
    actual = _field_value(data, grader["field"])
    expected = grader["equals"]
    return GraderResult(
        passed=actual == expected,
        message="field equals expected value" if actual == expected else "field does not equal expected value",
        details={"path": _rel(path), "field": grader["field"], "expected": expected, "actual": actual},
    )


def _grade_command(grader: dict[str, Any], *, allow_commands: bool) -> GraderResult:
    command = grader["command"]
    if not allow_commands:
        return GraderResult(
            passed=False,
            message="command grader skipped because --allow-commands was not set",
            details={"command": command},
        )

    cwd = _repo_path(grader.get("cwd", "."))
    expected_exit = int(grader.get("expected_exit", 0))
    timeout_seconds = int(grader.get("timeout_seconds", 120))
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return GraderResult(
            passed=False,
            message=f"command timed out after {timeout_seconds}s",
            details={"command": command, "cwd": _rel(cwd), "stdout": exc.stdout, "stderr": exc.stderr},
        )
    duration_ms = int((time.perf_counter() - started) * 1000)
    stdout_tail = (completed.stdout or "")[-2000:]
    stderr_tail = (completed.stderr or "")[-2000:]
    return GraderResult(
        passed=completed.returncode == expected_exit,
        message=(
            f"command exited {completed.returncode}"
            if completed.returncode == expected_exit
            else f"command exited {completed.returncode}, expected {expected_exit}"
        ),
        details={
            "command": command,
            "cwd": _rel(cwd),
            "duration_ms": duration_ms,
            "returncode": completed.returncode,
            "expected_exit": expected_exit,
            "stdout_tail": stdout_tail,
            "stderr_tail": stderr_tail,
        },
    )


def _run_grader(grader: dict[str, Any], *, allow_commands: bool) -> GraderResult:
    grader_type = grader["type"]
    try:
        if grader_type == "file_contains":
            return _grade_file_contains(grader)
        if grader_type == "file_not_contains":
            return _grade_file_not_contains(grader)
        if grader_type == "file_regex":
            return _grade_file_regex(grader)
        if grader_type == "json_field_equals":
            return _grade_json_field_equals(grader)
        if grader_type == "command":
            return _grade_command(grader, allow_commands=allow_commands)
    except EvalError as exc:
        return GraderResult(passed=False, message=str(exc), details={"type": grader_type})
    raise EvalError(f"unsupported grader type {grader_type!r}")


def _run_eval(eval_case: dict[str, Any], *, allow_commands: bool) -> EvalResult:
    started = time.perf_counter()
    graders = [_run_grader(grader, allow_commands=allow_commands) for grader in eval_case["graders"]]
    duration_ms = int((time.perf_counter() - started) * 1000)
    return EvalResult(
        eval_id=eval_case["id"],
        title=eval_case["title"],
        category=eval_case["category"],
        critical=eval_case["critical"],
        passed=all(grader.passed for grader in graders),
        graders=graders,
        duration_ms=duration_ms,
    )


def _result_to_dict(result: EvalResult) -> dict[str, Any]:
    return {
        "id": result.eval_id,
        "title": result.title,
        "category": result.category,
        "critical": result.critical,
        "passed": result.passed,
        "duration_ms": result.duration_ms,
        "graders": [
            {"passed": grader.passed, "message": grader.message, "details": grader.details}
            for grader in result.graders
        ],
    }


def _build_report(
    suite: dict[str, Any],
    suite_path: Path,
    results: list[EvalResult],
    *,
    started_at: str,
    duration_ms: int,
) -> dict[str, Any]:
    passed = sum(1 for result in results if result.passed)
    failed = len(results) - passed
    critical_failed = sum(1 for result in results if result.critical and not result.passed)
    return {
        "suite_id": suite["suite_id"],
        "suite_name": suite["name"],
        "suite_path": _rel(suite_path),
        "started_at": started_at,
        "completed_at": _utc_now(),
        "duration_ms": duration_ms,
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "critical_failed": critical_failed,
        },
        "results": [_result_to_dict(result) for result in results],
    }


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path = _repo_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", default=str(DEFAULT_SUITE), help="Path to an agent eval suite JSON file")
    parser.add_argument("--report", default=None, help="Optional JSON report output path")
    parser.add_argument(
        "--allow-commands",
        action="store_true",
        help="Allow command graders. Disabled by default to keep static guardrails safe.",
    )
    parser.add_argument("--json", action="store_true", help="Print the full JSON report to stdout")
    args = parser.parse_args()

    suite_path = _repo_path(args.suite)
    try:
        suite = _load_json(suite_path)
        _validate_suite(suite, suite_path)
        started_at = _utc_now()
        started = time.perf_counter()
        results = [_run_eval(eval_case, allow_commands=args.allow_commands) for eval_case in suite["evals"]]
        duration_ms = int((time.perf_counter() - started) * 1000)
        report = _build_report(suite, suite_path, results, started_at=started_at, duration_ms=duration_ms)
    except EvalError as exc:
        print(f"agent eval runner error: {exc}", file=sys.stderr)
        return 2

    if args.report:
        _write_report(Path(args.report), report)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        summary = report["summary"]
        print(
            f"{report['suite_id']}: {summary['passed']}/{summary['total']} passed, "
            f"{summary['failed']} failed, {summary['critical_failed']} critical failed"
        )
        for result in results:
            status = "PASS" if result.passed else "FAIL"
            critical = " critical" if result.critical else ""
            print(f"[{status}]{critical} {result.eval_id}: {result.title}")
            if not result.passed:
                for grader in result.graders:
                    if not grader.passed:
                        print(f"  - {grader.message}: {grader.details}")

    return 1 if report["summary"]["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
