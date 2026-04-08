#!/usr/bin/env bash
set -euo pipefail

# Orbital Inspect — Deployment Smoke Test
# Usage: ./smoke_test.sh [BASE_URL]
# Default: http://localhost:8000

BASE_URL="${1:-http://localhost:8000}"
PASS=0
FAIL=0
TOTAL=0

check() {
    local name="$1"
    local cmd="$2"
    TOTAL=$((TOTAL + 1))
    if eval "$cmd" > /dev/null 2>&1; then
        echo "  [PASS] $name"
        PASS=$((PASS + 1))
    else
        echo "  [FAIL] $name"
        FAIL=$((FAIL + 1))
    fi
}

echo "=== Orbital Inspect Smoke Test ==="
echo "Target: $BASE_URL"
echo ""

echo "--- Infrastructure ---"
check "Health endpoint" "curl -sf $BASE_URL/api/health"
check "Readiness endpoint" "curl -sf $BASE_URL/api/ready"
check "Metrics endpoint" "curl -sf $BASE_URL/api/metrics"
check "Prometheus metrics" "curl -sf $BASE_URL/api/metrics/prometheus | grep -q orbital_"

echo ""
echo "--- API v1 Routing ---"
check "OpenAPI spec" "curl -sf $BASE_URL/openapi.json | python3 -c 'import sys,json; d=json.load(sys.stdin); assert len(d[\"paths\"]) > 30'"
check "Portfolio endpoint" "curl -sf $BASE_URL/api/v1/portfolio"
check "Portfolio summary" "curl -sf $BASE_URL/api/v1/portfolio/summary"
check "Datasets list" "curl -sf $BASE_URL/api/v1/datasets"
check "Precedents list" "curl -sf $BASE_URL/api/v1/precedents"

echo ""
echo "--- Backward Compat ---"
check "Legacy /api/portfolio" "curl -sf $BASE_URL/api/portfolio"
check "Legacy /api/demos" "curl -sf $BASE_URL/api/demos"

echo ""
echo "--- Error Handling ---"
check "RFC 7807 error envelope" "curl -sf $BASE_URL/api/v1/analyses/nonexistent 2>&1 || curl -s $BASE_URL/api/v1/analyses/nonexistent | python3 -c 'import sys,json; d=json.load(sys.stdin); assert d[\"type\"] == \"/errors/not-found\"'"

echo ""
echo "--- Demo Mode ---"
check "Demo catalog" "curl -sf $BASE_URL/api/v1/demos | python3 -c 'import sys,json; d=json.load(sys.stdin); assert len(d[\"demos\"]) >= 1'"

echo ""
echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="
if [ "$FAIL" -gt 0 ]; then
    echo "SMOKE TEST FAILED"
    exit 1
fi
echo "SMOKE TEST PASSED"
