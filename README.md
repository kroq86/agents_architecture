# Minimal Local AI Agent Backend

Single-service FastAPI backend with a bounded agent loop, pluggable LLM client, typed tools, Jinja2 prompts, async SQLAlchemy, Alembic migrations, SSE streaming, and OpenTelemetry tracing.

## Architecture alignment ([`architecture.md`](architecture.md))

This repo implements the **minimal invariants** from the generic architecture doc: internal request IDs, coordinator-style orchestration, tool gateway with typed contracts, facts/manifest/transcript separation, findings/provenance/coverage gaps, bounded retries with error categories, observability (traces + Prometheus), short DB transactions (no LLM inside a transaction), and Jinja2 prompts with policy hooks outside prompts alone.

**Deferred by design** (single local service; add when product/deploy requires them): subagent runtime, async notification/webhook layer, full role-scoped tool inventory beyond task-type allowlists, multi-stage context compaction, background job execution, and enterprise identity (e.g. Cognito).

**Deterministic policy (§5.6):** task-type tool allowlists live in [`backend/app/services/runtime_policy.py`](backend/app/services/runtime_policy.py) and are enforced in [`backend/app/services/tool_gateway.py`](backend/app/services/tool_gateway.py) (`list_specs_for_task`, `invoke`), not only in prompts.

**Production interaction layer (§5.1):** optional in-app rate limits on `POST /chat` via SlowAPI (`RATE_LIMIT_ENABLED`, `CHAT_RATE_LIMIT` in Environment); for serious exposure, also put the API behind an API gateway or edge with auth and stricter quotas.

**Human review:** `GET /reviews` (default `status=pending`, or `status=all`); resolve via `PATCH /reviews/{id}` with `resolution` (and optional `resolver`, `status`). `app_hitl_queue_depth` counts `status=pending` only.

## Runtime contracts

- Agent action contract:
  - `finish`: return final answer.
  - `tool_call`: request a tool call; the server runs a bounded loop (see `MAX_TOOL_CALLS_PER_RUN`, default `1`) so multiple tool rounds are allowed when configured.
- Internal request contract:
  - `request_id`, `session_id`, `trace_id`, `task_type`, `input_payload`, `user_constraints`, `priority`, `deadline`, `attachments`.
- Tool result contract:
  - `success`, `is_error`, `error_category`, `is_retryable`, `result_type`, `payload`, `metadata`, `partial_results`, `attempted_action`, `suggested_next_steps`.
- Policy hooks:
  - `pre_execute`: validates tool name and args shape.
  - `normalize_result`: enforces standard tool result envelope.
- Session/state persistence:
  - `session_states`: current phase + manifest fields.
  - `facts_blocks`: persistent critical facts by key.
  - `scratchpads`: run summaries and intermediate artifacts.
- Transcript (audit lineage, separate from structured facts):
  - `run_transcript_events`: append-only ordered `user` / `tool_call` / `assistant` events with JSON payloads.

## Structure

```text
backend/
  app/
    api/
    core/
    db/
    models/
    observability/
    prompts/
    services/
    tools/
    main.py
  alembic/
    env.py
    versions/0001_initial.py
  alembic.ini
  pyproject.toml
  .env.example
```

## Environment

Copy and edit:

```bash
cp .env.example .env
```

Required for OpenAI mode:
- `OPENAI_API_KEY`
- `OPENAI_MODEL`

Core variables:
- `DATABASE_URL`
- `LLM_PROVIDER` (`openai` or `mock`)
- `OTEL_SERVICE_NAME`
- `OTEL_TRACES_EXPORTER` (`console` or `otlp`)
- `MAX_RETRY_ATTEMPTS` (default `2`)
- `MAX_TOOL_CALLS_PER_RUN` (default `1`, minimum `1`)
- `OPENAI_MODEL_PRICES_JSON` (per-model token pricing map)
- `RATE_LIMIT_ENABLED` (default `false` for local; set `true` when exposing the API)
- `CHAT_RATE_LIMIT` (default `120/minute`; SlowAPI string, e.g. `60/minute`)
- `CORS_ORIGINS` — comma-separated browser origins; **empty** = no CORS middleware (safest default)
- `API_KEY` — optional; when set, `POST /chat`, `GET /runs/{id}`, `GET/PATCH /reviews` require `X-API-Key: <key>` or `Authorization: Bearer <key>` (`/healthz`, `/readyz`, `/metrics` stay open)
- `APP_ENV` — set `production` to hide internal error text on HTTP 500 responses

API errors use a stable JSON body: `{"detail": ..., "code": ...}` (`code` is `validation_error` for 422, `internal_error` for unhandled 500 in non-production).

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Migrations

```bash
alembic upgrade head
```

## Tests

```bash
cd backend
pip install -e ".[dev]"
PYTHONPATH=. pytest -q
```

## Run (Gunicorn first)

```bash
gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 2 -b 0.0.0.0:8000 --chdir .
```

Dev-only direct Uvicorn:

```bash
uvicorn app.main:app --reload
```

## MCP Verifier (next iterations)

Project-level MCP config is set in:
- `.cursor/mcp.json`

It uses Docker image:
- `ghcr.io/kroq86/rule-based-verifier:sha-54a70fe`

Pre-pull locally:

```bash
docker pull ghcr.io/kroq86/rule-based-verifier:sha-54a70fe
```

After pull, reload Cursor MCP servers so `rule-based-verifier` is available for verifier-driven checks in future iterations.

## API

### POST `/chat` (SSE)

```bash
curl -N -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"search docs for async transactions"}'
```

Optional request contract fields:
- `session_id`
- `task_type`
- `user_constraints`
- `priority`
- `deadline`
- `attachments`

Example events:

```text
event: run_started
data: "0b04f968-c08a-4864-8b76-cf56369b7214"

event: message
data: "Here is what I found..."

event: run_completed
data: "0b04f968-c08a-4864-8b76-cf56369b7214"
```

### GET `/runs/{id}`

```bash
curl http://127.0.0.1:8000/runs/<run_id>
```

Response includes `request_id`, `session_id`, `trace_id`, `task_type`, `transcript_events` (ordered audit trail), `messages`, and `tool_calls`.

## Strict E2E Guard (`doc.md`)

Run this guard to fail fast unless the system actually uses `doc.md` through the tool path:

```bash
source .venv/bin/activate
python3 scripts/e2e_doc_guard.py
```

## Metrics and Reliability

Prometheus metrics endpoint:

```bash
curl -sS http://127.0.0.1:8000/metrics
```

Definitions live in [`backend/app/observability/metrics.py`](backend/app/observability/metrics.py).

### Most valuable metrics

| Priority | Metric | Why |
|----------|--------|-----|
| 1 | `app_chat_stream_duration_seconds` (`outcome`) | **User-perceived** latency for `POST /chat` (full SSE until completion). Use this for SLOs — **not** `app_request_latency_seconds` for `/chat` (middleware only sees response start). |
| 2 | `app_llm_latency_seconds` (`phase`: `first_call`, `follow_call`) | Where **model latency** sits in the loop; compare phases when tuning prompts or `MAX_TOOL_CALLS_PER_RUN`. |
| 3 | `app_tool_latency_seconds` (`tool_name`) | **Retrieval / tool** cost vs LLM; often small next to OpenAI RTT. |
| 4 | `app_tool_calls_per_run` (`outcome`) | **Depth of the agent loop** (tool rounds per run); rises when you allow more steps or the model keeps calling tools. |
| 5 | `app_quality_kpi_total` (`kpi`), `app_escalation_total` (`trigger_class`) | **Quality / policy pressure** (coverage gaps, escalations). |
| 6 | `app_hitl_queue_depth` | **Human review backlog** (pending items only). |
| 7 | `app_llm_tokens_total`, `app_llm_cost_usd_total` (`model`) | **Cost** vs quality (tokens and estimated USD). |
| 8 | `app_retry_total`, `app_error_total` | **Reliability** (retries and errors by `operation` / `stage`). |

**Reading histograms:** `*_sum` and `*_count` are **cumulative** for the process lifetime. Approximate mean observation time = `_sum` / `_count`. Several runs add up in `_sum` — do not treat `_sum` alone as “one request took that many seconds.” In Grafana, prefer `rate()` and `histogram_quantile` over raw sums.

Other useful metrics: `app_request_latency_seconds` (non-`/chat` routes), `app_requests_total`, `app_inflight_requests`, `app_tool_calls_total`.

Retry policy:
- bounded async retries for LLM and tool execution
- controlled by `MAX_RETRY_ATTEMPTS` in `.env` (default `2`)

Failure drills for retry/error metrics:

```bash
curl -N -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"drill transient","user_constraints":{"failure_drill":"transient_llm"}}'
```

```bash
curl -N -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"drill validation","user_constraints":{"failure_drill":"validation_tool"}}'
```

Quality/review persistence:
- `findings`, `provenances`, `coverage_gaps`, `human_review_items` (with `status` default `pending`; optional `resolved_at`, `resolution`, `resolver` for lifecycle)
- generated during orchestration to track evidence and escalation state
- `app_hitl_queue_depth` counts only `status=pending` review items

Prometheus rules:
- `observability/prometheus/rules/latency_slo.yml`
- `observability/prometheus/rules/reliability.yml`

## Retrieval Growth Plan

Current retrieval ranks non-empty lines in `doc.md` with **BM25** (Okapi), with a legacy “all query tokens appear on the line” fallback when BM25 returns no scored hits.

Planned progression as corpus/complexity grows:

1. **BM25 (implemented)** plus legacy line fallback; next tuning: chunking, stemming, larger corpora.
   - Adopt when document count grows and simple substring matching becomes noisy.
   - Goal: better ranking quality with minimal latency/cost overhead.
2. Local embedding index (FAISS or lightweight local index)
   - Adopt when semantic queries frequently miss lexical matches.
   - Goal: improve recall for meaning-based queries while staying local-first.
3. Full vector database
   - Adopt only when scale/operational needs require ANN service features
     (large corpora, metadata filtering, multi-tenant retrieval, higher QPS).
   - Goal: production retrieval infrastructure, not default for small local setups.

Notes:
- Prefer incremental upgrades and benchmark each step on latency, recall, and answer quality before moving to the next stage.

HTTP label hygiene (`path` on `app_request_latency_seconds` and `app_requests_total`):
- Labels use the **matched route template** after the request is routed (e.g. `/runs/{run_id}`), not literal URLs with UUIDs, so Prometheus cardinality stays bounded.
- A regex fallback maps `/runs/<uuid>` to `/runs/{run_id}` if `scope["route"]` is missing.

