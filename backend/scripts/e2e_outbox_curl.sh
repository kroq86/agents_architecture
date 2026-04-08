#!/usr/bin/env bash
# Curl-based E2E for transactional outbox (async chat).
#
# Prerequisites (same machine or same compose stack):
#   1) Database migrated: from the backend dir run once
#        cd backend && alembic upgrade head
#      (or: export DATABASE_URL=... && RUN_ALEMBIC_UPGRADE=1 when running this script)
#   2) API: uvicorn with the same DATABASE_URL and LLM_PROVIDER=mock
#   3) Worker (same DATABASE_URL / LLM_PROVIDER), from backend with venv activated:
#        PYTHONPATH=. python3 -m app.worker
#      or: PYTHONPATH=. python3 -m app.worker.main
#      or: agent-worker
#
# Run this script from the repo root or from backend; path is always:
#   backend/scripts/e2e_outbox_curl.sh
#
# Usage:
#   export BASE_URL=http://127.0.0.1:8000
#   ./scripts/e2e_outbox_curl.sh
#
# Optional:
#   MAX_WAIT_SECONDS=120 ./scripts/e2e_outbox_curl.sh
#   RUN_ALEMBIC_UPGRADE=1 DATABASE_URL=sqlite+aiosqlite:///./local.db ./scripts/e2e_outbox_curl.sh
#   PROMETHEUS_MULTIPROC_DIR=/tmp/platform-prom ./scripts/e2e_outbox_curl.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
MAX_WAIT="${MAX_WAIT_SECONDS:-90}"
PROM_DIR="${PROMETHEUS_MULTIPROC_DIR:-}"

die() {
  echo "ERROR: $*" >&2
  exit 1
}

json_field() {
  python3 -c 'import json,sys; print(json.load(sys.stdin)[sys.argv[1]])' "$1"
}

if [[ "${RUN_ALEMBIC_UPGRADE:-0}" == "1" ]]; then
  [[ -n "${DATABASE_URL:-}" ]] || die "RUN_ALEMBIC_UPGRADE=1 requires DATABASE_URL"
  echo "==> alembic upgrade head (backend: ${BACKEND_DIR})"
  (cd "${BACKEND_DIR}" && alembic upgrade head)
fi

if [[ -n "${PROM_DIR}" ]]; then
  echo "==> expecting multi-process metrics in ${PROM_DIR}"
fi

echo "==> GET ${BASE_URL}/healthz"
curl -sfS "${BASE_URL}/healthz" | python3 -m json.tool >/dev/null || die "healthz failed (is the API up?)"

echo "==> POST ${BASE_URL}/chat/async"
tmp="$(mktemp)"
code="$(curl -sS -o "${tmp}" -w "%{http_code}" -X POST "${BASE_URL}/chat/async" \
  -H "Content-Type: application/json" \
  -d '{"message":"curl e2e outbox"}')" || die "POST /chat/async failed"
body="$(cat "${tmp}")"
rm -f "${tmp}"

[[ "${code}" == "202" ]] || die "expected HTTP 202 from /chat/async, got ${code}: ${body}"

run_id="$(echo "${body}" | json_field run_id)"
status="$(echo "${body}" | json_field status)"
[[ "${status}" == "queued" ]] || die "expected status queued in async response, got: ${status}"

echo "    run_id=${run_id}"
echo "==> Poll GET ${BASE_URL}/runs/${run_id} until status=completed (max ${MAX_WAIT}s; worker must be running)"

deadline=$((SECONDS + MAX_WAIT))
while true; do
  rtmp="$(mktemp)"
  rcode="$(curl -sS -o "${rtmp}" -w "%{http_code}" "${BASE_URL}/runs/${run_id}")" || die "GET /runs failed"
  rbody="$(cat "${rtmp}")"
  rm -f "${rtmp}"
  [[ "${rcode}" == "200" ]] || die "GET /runs expected 200, got ${rcode}: ${rbody}"

  st="$(echo "${rbody}" | json_field status)"
  if [[ "${st}" == "completed" ]]; then
    echo "    status=completed"
    break
  fi
  if [[ "${st}" == "failed" ]]; then
    die "run failed: ${rbody}"
  fi
  if (( SECONDS >= deadline )); then
    die "timed out after ${MAX_WAIT}s waiting for completed (is the worker running with the same DATABASE_URL? try: PYTHONPATH=. python3 -m app.worker)"
  fi
  sleep 0.5
done

echo "==> GET ${BASE_URL}/metrics (outbox lines)"
outbox_lines="$(curl -sfS "${BASE_URL}/metrics" | grep -E '^app_outbox_(events_processed_total|pipeline_seconds_(sum|count))' || true)"
echo "${outbox_lines}"
echo "${outbox_lines}" | grep -q 'app_outbox_events_processed_total{' || die "missing app_outbox_events_processed_total samples in /metrics"
echo "${outbox_lines}" | grep -q 'app_outbox_pipeline_seconds_count{' || die "missing app_outbox_pipeline_seconds_count samples in /metrics"

echo "OK: outbox curl E2E passed (async enqueue + worker + completed run + metrics visible)."
