"""Lexical BM25 ranking over line-level documents (no external deps)."""

from __future__ import annotations

import math
import re
from pathlib import Path

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in _TOKEN_RE.finditer(text)]


def _avgdl(lengths: list[int]) -> float:
    if not lengths:
        return 0.0
    return sum(lengths) / len(lengths)


def bm25_score(
    query_tokens: list[str],
    doc_tokens: list[str],
    *,
    doc_freqs: dict[str, int],
    num_docs: int,
    avgdl: float,
    k1: float = 1.5,
    b: float = 0.75,
) -> float:
    """Okapi BM25 for a single document."""
    if not query_tokens or not doc_tokens:
        return 0.0
    dl = len(doc_tokens)
    freqs: dict[str, int] = {}
    for t in doc_tokens:
        freqs[t] = freqs.get(t, 0) + 1
    score = 0.0
    for q in query_tokens:
        n_qi = doc_freqs.get(q, 0)
        if n_qi <= 0:
            continue
        idf = math.log((num_docs - n_qi + 0.5) / (n_qi + 0.5) + 1.0)
        f = freqs.get(q, 0)
        denom = f + k1 * (1.0 - b + b * (dl / avgdl) if avgdl > 0 else 1.0)
        if denom <= 0:
            continue
        score += idf * (f * (k1 + 1.0)) / denom
    return score


def search_lines_bm25(
    doc_path: Path,
    query: str,
    max_results: int,
) -> list[dict[str, object]]:
    """Rank non-empty lines by BM25 over query tokens."""
    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    lines: list[tuple[int, str]] = []
    with doc_path.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            stripped = line.strip()
            if stripped:
                lines.append((idx, stripped))

    if not lines:
        return []

    tokenized_docs: list[list[str]] = [tokenize(text) for _, text in lines]
    lengths = [len(t) for t in tokenized_docs]
    avgdl = _avgdl(lengths)

    doc_freqs: dict[str, int] = {}
    for tokens in tokenized_docs:
        seen = set(tokens)
        for t in seen:
            doc_freqs[t] = doc_freqs.get(t, 0) + 1

    num_docs = len(lines)
    scored: list[tuple[float, int, str]] = []
    for (line_no, text), tokens in zip(lines, tokenized_docs, strict=True):
        s = bm25_score(
            query_tokens,
            tokens,
            doc_freqs=doc_freqs,
            num_docs=num_docs,
            avgdl=avgdl,
        )
        scored.append((s, line_no, text))

    scored.sort(key=lambda x: x[0], reverse=True)
    out: list[dict[str, object]] = []
    for s, line_no, text in scored[:max_results]:
        if s <= 0:
            continue
        out.append(
            {
                "id": f"doc-line-{line_no}",
                "title": "doc.md",
                "line_number": line_no,
                "snippet": text[:300],
                "score": round(float(s), 6),
            }
        )
    return out
