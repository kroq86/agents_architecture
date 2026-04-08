"""Shared helpers for end-to-end tests (SSE parsing, repo paths)."""

from __future__ import annotations

import json
from pathlib import Path

# backend/tests -> repo root
REPO_ROOT = Path(__file__).resolve().parents[2]


def sse_run_completed_run_id(sse_body: str) -> str | None:
    """Extract run id from `run_completed` SSE event (same shape as `scripts/e2e_doc_guard.py`)."""
    run_id: str | None = None
    event: str | None = None
    for line in sse_body.splitlines():
        if line.startswith("event: "):
            event = line.split(":", 1)[1].strip()
            continue
        if line.startswith("data: ") and event == "run_completed":
            raw = line.split(":", 1)[1].strip()
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, str):
                run_id = parsed
            break
    return run_id


def doc_md_exists() -> bool:
    return (REPO_ROOT / "doc.md").is_file()


def prometheus_counter_sum(text: str, metric_prefix: str) -> float:
    """Sum all sample values for lines starting with ``metric_prefix{`` (OpenMetrics exposition)."""
    total = 0.0
    for line in text.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        if line.startswith(metric_prefix + "{"):
            total += float(line.split()[-1])
    return total


def prometheus_histogram_mean_seconds(text: str, name: str) -> float | None:
    """Approximate mean observation time: ``_sum / _count`` for histogram ``name`` (all label sets)."""
    total_sum, total_count = prometheus_histogram_total_sum_count(text, name)
    if total_count == 0:
        return None
    return total_sum / total_count


def prometheus_histogram_total_sum_count(text: str, name: str) -> tuple[float, float]:
    """Aggregate ``_sum`` and ``_count`` across all label values (OpenMetrics exposition)."""
    total_sum = 0.0
    total_count = 0.0
    for line in text.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        if line.startswith(f"{name}_sum"):
            total_sum += float(line.split()[-1])
        elif line.startswith(f"{name}_count"):
            total_count += float(line.split()[-1])
    return total_sum, total_count
