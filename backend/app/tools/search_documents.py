import asyncio
import re
from pathlib import Path

from pydantic import BaseModel, Field

from app.tools.base import Tool
from app.tools.retrieval_bm25 import search_lines_bm25


class SearchDocumentsInput(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    max_results: int = Field(default=5, ge=1, le=20)


class SearchDocumentsTool(Tool):
    name = "search_documents"
    description = "Searches local document corpus by plain text query."
    input_schema = SearchDocumentsInput

    async def execute(self, payload: SearchDocumentsInput) -> dict[str, object]:
        doc_path = Path(__file__).resolve().parents[3] / "doc.md"
        if not doc_path.exists():
            return {
                "success": False,
                "is_error": True,
                "error_category": "business",
                "is_retryable": False,
                "result_type": "document_search",
                "payload": {"query": payload.query, "matches": []},
                "metadata": {"source": str(doc_path), "reason": "file_not_found"},
                "partial_results": [],
                "attempted_action": "search_documents",
                "suggested_next_steps": ["Ensure doc.md exists at repository root."],
            }

        matches = await asyncio.to_thread(
            self._search_file_bm25_then_legacy,
            doc_path,
            payload.query,
            payload.max_results,
        )
        return {
            "success": True,
            "is_error": False,
            "error_category": None,
            "is_retryable": False,
            "result_type": "document_search",
            "payload": {
                "query": payload.query,
                "matches": matches,
            },
            "metadata": {"source": str(doc_path), "total_matches": len(matches)},
            "partial_results": [],
            "attempted_action": "search_documents",
            "suggested_next_steps": [],
        }

    @staticmethod
    def _search_file_bm25_then_legacy(doc_path: Path, query: str, max_results: int) -> list[dict[str, object]]:
        ranked = search_lines_bm25(doc_path, query, max_results)
        if ranked:
            return ranked
        return SearchDocumentsTool._legacy_all_tokens_in_line(doc_path, query, max_results)

    @staticmethod
    def _legacy_all_tokens_in_line(doc_path: Path, query: str, max_results: int) -> list[dict[str, object]]:
        query_tokens = [t for t in re.split(r"\s+", query.lower().strip()) if t]
        results: list[dict[str, object]] = []
        with doc_path.open("r", encoding="utf-8") as f:
            for idx, line in enumerate(f, start=1):
                hay = line.strip()
                if not hay:
                    continue
                hay_l = hay.lower()
                if query_tokens and all(token in hay_l for token in query_tokens):
                    results.append(
                        {
                            "id": f"doc-line-{idx}",
                            "title": "doc.md",
                            "line_number": idx,
                            "snippet": hay[:300],
                        }
                    )
                    if len(results) >= max_results:
                        break
        return results

