import time
from collections.abc import AsyncGenerator

from opentelemetry import trace
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.schemas import InternalRequest
from app.observability.metrics import (
    ERROR_COUNT,
    ESCALATION_COUNT,
    HITL_QUEUE_DEPTH,
    LLM_LATENCY_SECONDS,
    QUALITY_KPI_COUNT,
    TOOL_CALLS_PER_RUN,
    observe_llm_usage,
)
from app.prompts.environment import build_prompt_environment
from app.services.llm.base import LLMClient
from app.services.repositories.runs import RunRepository
from app.services.retry import RetryableOperationError, retry_async
from app.services.repositories.state import SessionStateRepository
from app.services.tool_gateway import ToolGateway
from app.tools.base import Tool, ToolResult

tracer = trace.get_tracer(__name__)

BUDGET_EXCEEDED_MSG = (
    "This run reached the maximum number of tool calls allowed. "
    "Narrow your request or raise MAX_TOOL_CALLS_PER_RUN."
)


class AgentOrchestrator:
    def __init__(self, llm: LLMClient, tool_gateway: ToolGateway) -> None:
        self._llm = llm
        self._tool_gateway = tool_gateway
        self._prompt_env = build_prompt_environment()
        self._max_retry_attempts = get_settings().max_retry_attempts
        self._max_tool_calls_per_run = get_settings().max_tool_calls_per_run

    @staticmethod
    def _fast_tool_answer(tool_output: dict) -> str | None:
        if tool_output.get("result_type") != "document_search":
            return None
        payload = tool_output.get("payload") or {}
        matches = payload.get("matches") or []
        if not matches:
            return None
        first = matches[0]
        snippet = (first.get("snippet") or "").strip()
        if snippet:
            return snippet
        return None

    async def run(
        self,
        session: AsyncSession,
        request: InternalRequest,
    ) -> AsyncGenerator[dict[str, str], None]:
        tool_calls_used = 0
        stream_outcome = "completed"
        repo = RunRepository(session)
        state_repo = SessionStateRepository(session)
        user_id = request.input_payload.get("user_id")
        user_input = request.input_payload.get("message", "")
        drill = request.user_constraints.get("failure_drill")
        drill_flags = {"llm_once": False, "tool_once": False}
        unregistered_tool = False
        tool_loop_exit: str | None = None

        try:
            async with session.begin():
                state = await state_repo.get_or_create(request.session_id)
                run = await repo.create_run(
                    user_id=user_id,
                    input_text=user_input,
                    request_id=request.request_id,
                    session_id=request.session_id,
                    trace_id=request.trace_id,
                    task_type=request.task_type,
                    user_constraints=request.user_constraints,
                    priority=request.priority,
                    deadline=request.deadline,
                    attachments=request.attachments,
                )
                await repo.add_message(run.id, "user", user_input)
                await repo.append_transcript_event(run.id, "user", {"text": user_input})
                await state_repo.upsert_fact(
                    state.id,
                    key="last_user_input",
                    value={"text": user_input, "request_id": request.request_id},
                )

            prompt = self._prompt_env.get_template("chat.j2").render(
                user_input=user_input,
                tool_result=None,
            )

            with tracer.start_as_current_span("llm.first_call"):
                llm_start = time.perf_counter()

                async def first_llm_call():
                    if drill == "always_unknown_llm":
                        raise RetryableOperationError(
                            "simulated permanent unknown llm failure",
                            error_category="unknown",
                        )
                    if drill == "transient_llm" and not drill_flags["llm_once"]:
                        drill_flags["llm_once"] = True
                        raise RetryableOperationError(
                            "simulated transient llm failure",
                            error_category="transient",
                        )
                    if drill == "unknown_llm" and not drill_flags["llm_once"]:
                        drill_flags["llm_once"] = True
                        raise RetryableOperationError(
                            "simulated unknown llm failure",
                            error_category="unknown",
                        )
                    return await self._llm.complete(
                        prompt,
                        self._tool_gateway.list_specs_for_task(request.task_type),
                    )

                llm_reply = await retry_async(
                    operation="llm.first_call",
                    max_attempts=self._max_retry_attempts,
                    call=first_llm_call,
                )
                LLM_LATENCY_SECONDS.labels(phase="first_call").observe(time.perf_counter() - llm_start)
                observe_llm_usage(
                    model=llm_reply.model or "unknown",
                    input_tokens=llm_reply.input_tokens,
                    output_tokens=llm_reply.output_tokens,
                    total_tokens=llm_reply.total_tokens,
                    estimated_cost_usd=llm_reply.estimated_cost_usd,
                )

            yield {"event": "run_started", "data": run.id}

            final_text = llm_reply.text

            async def single_attempt(tool: Tool, parsed: BaseModel) -> ToolResult:
                if drill == "always_validation_tool":
                    raise RetryableOperationError(
                        "simulated permanent validation tool failure",
                        error_category="validation",
                    )
                if drill == "transient_tool" and not drill_flags["tool_once"]:
                    drill_flags["tool_once"] = True
                    raise RetryableOperationError(
                        "simulated transient tool failure",
                        error_category="transient",
                    )
                if drill == "validation_tool" and not drill_flags["tool_once"]:
                    drill_flags["tool_once"] = True
                    raise RetryableOperationError(
                        "simulated validation tool failure",
                        error_category="validation",
                    )
                return await tool.execute(parsed)

            while llm_reply.action == "tool_call" and tool_calls_used < self._max_tool_calls_per_run:
                tool_name = llm_reply.tool_name or ""
                args = llm_reply.tool_args or {}

                gw = await self._tool_gateway.invoke(
                    tool_name,
                    args,
                    task_type=request.task_type,
                    single_attempt=single_attempt,
                )

                if gw.policy_denied:
                    unregistered_tool = True
                    tool_loop_exit = "policy_denied"
                    final_text = gw.unregistered_message or (
                        f"Tool '{tool_name}' is not permitted for this task."
                    )
                    ERROR_COUNT.labels(stage="tool.policy", error_category="permission").inc()
                    QUALITY_KPI_COUNT.labels(kpi="coverage_gap").inc()
                    async with session.begin():
                        await repo.add_coverage_gap(
                            run_id=run.id,
                            gap_type="tool_policy_denied",
                            description=final_text,
                            severity="medium",
                            metadata={"tool_name": tool_name, "task_type": request.task_type},
                        )
                        await repo.add_review_item(
                            run_id=run.id,
                            trigger_class="tool_policy_denied",
                            case_summary=final_text,
                            uncertainty="runtime policy allowlist",
                            attempted_actions=[{"tool_name": tool_name, "task_type": request.task_type}],
                        )
                    ESCALATION_COUNT.labels(trigger_class="tool_policy_denied").inc()
                    break

                if not gw.registered:
                    unregistered_tool = True
                    tool_loop_exit = "unregistered"
                    final_text = gw.unregistered_message or f"Requested tool '{tool_name}' is not registered."
                    ERROR_COUNT.labels(stage="tool.lookup", error_category="validation").inc()
                    QUALITY_KPI_COUNT.labels(kpi="coverage_gap").inc()
                    async with session.begin():
                        await repo.add_coverage_gap(
                            run_id=run.id,
                            gap_type="tool_not_registered",
                            description=final_text,
                            severity="medium",
                            metadata={"tool_name": tool_name},
                        )
                        await repo.add_review_item(
                            run_id=run.id,
                            trigger_class="tool_not_registered",
                            case_summary=final_text,
                            uncertainty="tool lookup failed",
                            attempted_actions=[{"tool_name": tool_name}],
                        )
                    ESCALATION_COUNT.labels(trigger_class="tool_not_registered").inc()
                    break

                tool_calls_used += 1
                tool_output = gw.normalized
                assert tool_output is not None

                async with session.begin():
                    await repo.add_tool_call(
                        run_id=run.id,
                        tool_name=tool_name,
                        tool_input=args,
                        tool_output=tool_output,
                    )
                    await repo.append_transcript_event(
                        run.id,
                        "tool_call",
                        {
                            "tool_name": tool_name,
                            "args": args,
                            "success": bool(tool_output.get("success")),
                        },
                    )

                follow_prompt = self._prompt_env.get_template("chat.j2").render(
                    user_input=user_input,
                    tool_result=tool_output,
                )
                fast_answer = self._fast_tool_answer(tool_output)
                if fast_answer is not None:
                    final_text = fast_answer
                    first_match = ((tool_output.get("payload") or {}).get("matches") or [{}])[0]
                    provenance = {
                        "claim": final_text,
                        "source_id": first_match.get("id"),
                        "source_name": (tool_output.get("metadata") or {}).get("source", "tool_output"),
                        "source_locator": f"line:{first_match.get('line_number')}"
                        if first_match.get("line_number")
                        else None,
                        "relevant_excerpt": first_match.get("snippet"),
                        "retrieval_timestamp": None,
                    }
                    async with session.begin():
                        await repo.add_finding_with_provenance(
                            run_id=run.id,
                            category="answer",
                            claim=final_text,
                            supporting_evidence=first_match.get("snippet"),
                            confidence=0.8,
                            status="final",
                            coverage_scope="tool-backed",
                            metadata={"tool_name": tool_name},
                            provenance=provenance,
                        )
                        matches = (tool_output.get("payload") or {}).get("matches") or []
                        if not matches:
                            QUALITY_KPI_COUNT.labels(kpi="coverage_gap").inc()
                            await repo.add_coverage_gap(
                                run_id=run.id,
                                gap_type="missing_evidence",
                                description="Tool executed but returned zero matches.",
                                severity="high",
                                metadata={"tool_name": tool_name, "query": args.get("query")},
                            )
                            await repo.add_review_item(
                                run_id=run.id,
                                trigger_class="coverage_gap",
                                case_summary="No evidence found for requested query.",
                                uncertainty="tool returned no matches",
                                attempted_actions=[{"tool_name": tool_name, "args": args}],
                            )
                            ESCALATION_COUNT.labels(trigger_class="coverage_gap").inc()
                    tool_loop_exit = "fast_path"
                    break

                with tracer.start_as_current_span("llm.follow_call"):
                    llm2_start = time.perf_counter()
                    llm_reply = await retry_async(
                        operation="llm.follow_call",
                        max_attempts=self._max_retry_attempts,
                        call=lambda: self._llm.complete(
                            follow_prompt,
                            self._tool_gateway.list_specs_for_task(request.task_type),
                        ),
                    )
                    LLM_LATENCY_SECONDS.labels(phase="follow_call").observe(time.perf_counter() - llm2_start)
                    observe_llm_usage(
                        model=llm_reply.model or "unknown",
                        input_tokens=llm_reply.input_tokens,
                        output_tokens=llm_reply.output_tokens,
                        total_tokens=llm_reply.total_tokens,
                        estimated_cost_usd=llm_reply.estimated_cost_usd,
                    )
                final_text = llm_reply.text

                first_match = ((tool_output.get("payload") or {}).get("matches") or [{}])[0]
                provenance = {
                    "claim": final_text,
                    "source_id": first_match.get("id"),
                    "source_name": (tool_output.get("metadata") or {}).get("source", "tool_output"),
                    "source_locator": f"line:{first_match.get('line_number')}"
                    if first_match.get("line_number")
                    else None,
                    "relevant_excerpt": first_match.get("snippet"),
                    "retrieval_timestamp": None,
                }
                async with session.begin():
                    await repo.add_finding_with_provenance(
                        run_id=run.id,
                        category="answer",
                        claim=final_text,
                        supporting_evidence=first_match.get("snippet"),
                        confidence=0.8,
                        status="final",
                        coverage_scope="tool-backed",
                        metadata={"tool_name": tool_name},
                        provenance=provenance,
                    )
                    matches = (tool_output.get("payload") or {}).get("matches") or []
                    if not matches:
                        QUALITY_KPI_COUNT.labels(kpi="coverage_gap").inc()
                        await repo.add_coverage_gap(
                            run_id=run.id,
                            gap_type="missing_evidence",
                            description="Tool executed but returned zero matches.",
                            severity="high",
                            metadata={"tool_name": tool_name, "query": args.get("query")},
                        )
                        await repo.add_review_item(
                            run_id=run.id,
                            trigger_class="coverage_gap",
                            case_summary="No evidence found for requested query.",
                            uncertainty="tool returned no matches",
                            attempted_actions=[{"tool_name": tool_name, "args": args}],
                        )
                        ESCALATION_COUNT.labels(trigger_class="coverage_gap").inc()

                if llm_reply.action != "tool_call":
                    tool_loop_exit = "llm_finish"
                    break

            if (
                tool_loop_exit is None
                and llm_reply.action == "tool_call"
                and tool_calls_used >= self._max_tool_calls_per_run
            ):
                final_text = BUDGET_EXCEEDED_MSG
                stream_outcome = "budget_exhausted"
                QUALITY_KPI_COUNT.labels(kpi="coverage_gap").inc()
                async with session.begin():
                    await repo.add_coverage_gap(
                        run_id=run.id,
                        gap_type="tool_budget_exhausted",
                        description=final_text,
                        severity="medium",
                        metadata={"max_tool_calls": self._max_tool_calls_per_run},
                    )
                    await repo.add_review_item(
                        run_id=run.id,
                        trigger_class="tool_budget_exhausted",
                        case_summary=final_text,
                        uncertainty="model requested another tool after budget",
                        attempted_actions=[],
                    )
                ESCALATION_COUNT.labels(trigger_class="tool_budget_exhausted").inc()

            if (
                not unregistered_tool
                and tool_calls_used == 0
                and llm_reply.action != "tool_call"
            ):
                async with session.begin():
                    await repo.add_finding_with_provenance(
                        run_id=run.id,
                        category="answer",
                        claim=final_text,
                        supporting_evidence=None,
                        confidence=0.5,
                        status="final",
                        coverage_scope="no-tool",
                        metadata={},
                        provenance=None,
                    )
                    if request.user_constraints.get("failure_drill") == "coverage_gap":
                        QUALITY_KPI_COUNT.labels(kpi="coverage_gap").inc()
                        await repo.add_coverage_gap(
                            run_id=run.id,
                            gap_type="forced_gap",
                            description="forced coverage gap drill",
                            severity="low",
                            metadata={"drill": True},
                        )
                        await repo.add_review_item(
                            run_id=run.id,
                            trigger_class="forced_drill",
                            case_summary="forced drill escalation",
                            uncertainty="synthetic",
                            attempted_actions=[],
                        )
                        ESCALATION_COUNT.labels(trigger_class="forced_drill").inc()

            async with session.begin():
                await repo.add_message(run.id, "assistant", final_text)
                await repo.complete_run(run, final_text)
                await state_repo.add_scratchpad(
                    state.id,
                    kind="run_summary",
                    content={"run_id": run.id, "final_text": final_text},
                )
                await state_repo.update_manifest(
                    state,
                    current_phase="completed",
                    completed_steps=["classify_task", "generate_answer"],
                    pending_steps=[],
                    next_action=None,
                )
                await repo.append_transcript_event(
                    run.id,
                    "assistant",
                    {"text": final_text, "tool_calls_used": tool_calls_used},
                )
                pending = await repo.pending_review_count()
                HITL_QUEUE_DEPTH.set(pending)

            yield {"event": "message", "data": final_text}
            yield {"event": "run_completed", "data": run.id}

        except Exception:
            stream_outcome = "error"
            raise
        finally:
            TOOL_CALLS_PER_RUN.labels(outcome=stream_outcome).observe(float(tool_calls_used))
