from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.message import Message
from app.models.quality import CoverageGap, Finding, HumanReviewItem, Provenance
from app.models.run import Run
from app.models.tool_call import ToolCall
from app.models.transcript import RunTranscriptEvent


class RunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_run(
        self,
        user_id: str | None,
        input_text: str,
        request_id: str,
        session_id: str,
        trace_id: str,
        task_type: str,
        user_constraints: dict,
        priority: str,
        deadline: str | None,
        attachments: list,
    ) -> Run:
        run = Run(
            user_id=user_id,
            input_text=input_text,
            request_id=request_id,
            session_id=session_id,
            trace_id=trace_id,
            task_type=task_type,
            user_constraints=user_constraints,
            priority=priority,
            deadline=deadline,
            attachments=attachments,
            status="started",
        )
        self.session.add(run)
        await self.session.flush()
        return run

    async def add_message(self, run_id: str, role: str, content: str) -> Message:
        msg = Message(run_id=run_id, role=role, content=content)
        self.session.add(msg)
        await self.session.flush()
        return msg

    async def add_tool_call(
        self,
        run_id: str,
        tool_name: str,
        tool_input: dict,
        tool_output: dict,
    ) -> ToolCall:
        tool_call = ToolCall(
            run_id=run_id,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=tool_output,
        )
        self.session.add(tool_call)
        await self.session.flush()
        return tool_call

    async def complete_run(self, run: Run, final_text: str) -> None:
        run.status = "completed"
        run.final_text = final_text
        run.finished_at = datetime.now(timezone.utc)
        await self.session.flush()

    async def add_finding_with_provenance(
        self,
        run_id: str,
        *,
        category: str,
        claim: str,
        supporting_evidence: str | None,
        confidence: float,
        status: str,
        coverage_scope: str | None,
        metadata: dict,
        provenance: dict | None,
    ) -> Finding:
        finding = Finding(
            run_id=run_id,
            category=category,
            claim=claim,
            supporting_evidence=supporting_evidence,
            confidence=confidence,
            status=status,
            coverage_scope=coverage_scope,
            metadata_json=metadata,
        )
        self.session.add(finding)
        await self.session.flush()
        if provenance:
            prov = Provenance(
                finding_id=finding.id,
                claim=provenance.get("claim", claim),
                source_id=provenance.get("source_id"),
                source_name=provenance.get("source_name", "unknown"),
                source_locator=provenance.get("source_locator"),
                relevant_excerpt=provenance.get("relevant_excerpt"),
                publication_or_effective_date=provenance.get("publication_or_effective_date"),
                retrieval_timestamp=provenance.get("retrieval_timestamp"),
            )
            self.session.add(prov)
            await self.session.flush()
        return finding

    async def add_coverage_gap(
        self,
        run_id: str,
        *,
        gap_type: str,
        description: str,
        severity: str = "medium",
        metadata: dict | None = None,
    ) -> CoverageGap:
        gap = CoverageGap(
            run_id=run_id,
            gap_type=gap_type,
            description=description,
            severity=severity,
            metadata_json=metadata or {},
        )
        self.session.add(gap)
        await self.session.flush()
        return gap

    async def add_review_item(
        self,
        run_id: str,
        *,
        trigger_class: str,
        case_summary: str,
        uncertainty: str | None,
        attempted_actions: list | None = None,
    ) -> HumanReviewItem:
        item = HumanReviewItem(
            run_id=run_id,
            trigger_class=trigger_class,
            case_summary=case_summary,
            uncertainty=uncertainty,
            attempted_actions=attempted_actions or [],
        )
        self.session.add(item)
        await self.session.flush()
        return item

    async def pending_review_count(self) -> int:
        query = select(func.count(HumanReviewItem.id)).where(HumanReviewItem.status == "pending")
        result = await self.session.execute(query)
        return int(result.scalar_one() or 0)

    async def list_review_items(
        self,
        *,
        status: str | None = "pending",
        limit: int = 100,
    ) -> list[HumanReviewItem]:
        query = select(HumanReviewItem).order_by(HumanReviewItem.created_at.desc()).limit(limit)
        if status is not None and status != "all":
            query = query.where(HumanReviewItem.status == status)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_review_item(self, item_id: str) -> HumanReviewItem | None:
        return await self.session.get(HumanReviewItem, item_id)

    async def resolve_review_item(
        self,
        item_id: str,
        *,
        status: str,
        resolution: str,
        resolver: str | None,
    ) -> HumanReviewItem | None:
        item = await self.session.get(HumanReviewItem, item_id)
        if item is None:
            return None
        item.status = status
        item.resolution = resolution
        item.resolver = resolver
        item.resolved_at = datetime.now(timezone.utc)
        await self.session.flush()
        return item

    async def append_transcript_event(self, run_id: str, kind: str, payload: dict) -> RunTranscriptEvent:
        sub = select(func.coalesce(func.max(RunTranscriptEvent.seq), -1)).where(
            RunTranscriptEvent.run_id == run_id,
        )
        result = await self.session.execute(sub)
        next_seq = int(result.scalar_one() or -1) + 1
        row = RunTranscriptEvent(run_id=run_id, seq=next_seq, kind=kind, payload_json=payload)
        self.session.add(row)
        await self.session.flush()
        return row

    async def get_run(self, run_id: str) -> Run | None:
        query = (
            select(Run)
            .where(Run.id == run_id)
            .options(
                selectinload(Run.messages),
                selectinload(Run.tool_calls),
                selectinload(Run.transcript_events),
            )
        )
        result = await self.session.execute(query)
        return result.scalars().first()

