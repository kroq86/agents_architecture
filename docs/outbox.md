# Transactional outbox (async chat)

## API

- **`POST /chat`** — synchronous SSE stream (unchanged): runs the orchestrator in the API process.
- **`POST /chat/async`** — returns **202 Accepted** with `{ run_id, request_id, session_id, trace_id, status: "queued" }`. One database transaction creates the run (status `queued`), user message, transcript bootstrap, and an **`outbox_events`** row (`event_type=run_created`).

Poll **`GET /runs/{run_id}`** until `status` is `completed` or `failed`.

## Worker (separate process)

Run a second process that claims outbox rows with `FOR UPDATE SKIP LOCKED` and leases:

```bash
cd backend
source .venv/bin/activate
python -m app.worker
```

Environment (see [`backend/.env.example`](../backend/.env.example)):

| Variable | Purpose |
|----------|---------|
| `WORKER_ID` | Lease owner id (default `local-worker`) |
| `OUTBOX_LEASE_SECONDS` | Claim lease TTL |
| `WORKER_POLL_SECONDS` | Sleep when no rows to claim |
| `OUTBOX_RETRY_BACKOFF_SECONDS` | Delay before `retryable` rows are reclaimed |

Use the same `DATABASE_URL` and `LLM_PROVIDER` as the API (e.g. `mock` for tests).

For worker metrics to appear in API `/metrics`, run both processes with the same
`PROMETHEUS_MULTIPROC_DIR` (for example `/tmp/platform-prom`) and make sure the
directory exists before starting processes.

## Metrics

Prometheus counters: `app_outbox_events_processed_total`, `app_outbox_events_dead_total` (labels: `event_type`).

Histogram **`app_outbox_pipeline_seconds`** (label `event_type`): seconds from outbox row creation (`created_at`) until the worker successfully marks the row processed (after the orchestrator run finishes). Buckets: 0.01s through 60s.

**Average pipeline latency (PromQL)** — global mean over a scrape window:

```promql
rate(app_outbox_pipeline_seconds_sum[5m]) / rate(app_outbox_pipeline_seconds_count[5m])
```

Per `event_type`:

```promql
sum by (event_type) (rate(app_outbox_pipeline_seconds_sum[5m]))
  / sum by (event_type) (rate(app_outbox_pipeline_seconds_count[5m]))
```

## Curl E2E (live processes)

```bash
# Terminal 1 (API)
cd backend
source .venv/bin/activate
export DATABASE_URL=sqlite+aiosqlite:///./local.db
export LLM_PROVIDER=mock
export OTEL_TRACES_EXPORTER=none
export PROMETHEUS_MULTIPROC_DIR=/tmp/platform-prom
mkdir -p "$PROMETHEUS_MULTIPROC_DIR"
rm -f "$PROMETHEUS_MULTIPROC_DIR"/*
alembic upgrade head
PYTHONPATH=. python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Terminal 2 (worker)
cd backend
source .venv/bin/activate
export DATABASE_URL=sqlite+aiosqlite:///./local.db
export LLM_PROVIDER=mock
export OTEL_TRACES_EXPORTER=none
export PROMETHEUS_MULTIPROC_DIR=/tmp/platform-prom
PYTHONPATH=. python3 -m app.worker

# Terminal 3 (curl e2e)
cd backend
export BASE_URL=http://127.0.0.1:8000
./scripts/e2e_outbox_curl.sh
```

## Deep Debug UI

A separate frontend debug UI is available at `frontend/` (Vite + React). It reads
`/chat`, `/chat/async`, `/runs/{run_id}`, and `/metrics` and renders:

- chat timeline (SSE/polling/both)
- run inspector (messages, tool calls, transcript)
- request path metrics tables
- outbox counters and SLA (avg/p95)
- raw metrics explorer with filter

## Deferred (not implemented)

Live **SSE** or **Redis pub/sub** for token streaming on async runs is out of scope for this iteration; clients poll `GET /runs/{id}` for status and messages.
