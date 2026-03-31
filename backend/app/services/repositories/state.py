from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.session_state import FactsBlock, Scratchpad, SessionState


class SessionStateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create(self, session_id: str) -> SessionState:
        stmt = (
            select(SessionState)
            .where(SessionState.session_id == session_id)
            .options(selectinload(SessionState.facts), selectinload(SessionState.scratchpads))
        )
        result = await self.session.execute(stmt)
        state = result.scalars().first()
        if state:
            return state

        state = SessionState(
            session_id=session_id,
            current_phase="intake",
            completed_steps=[],
            pending_steps=["classify_task", "generate_answer"],
            artifacts=[],
            known_blockers=[],
            next_action="classify_task",
        )
        self.session.add(state)
        await self.session.flush()
        return state

    async def upsert_fact(self, session_state_id: str, key: str, value: dict) -> FactsBlock:
        stmt = select(FactsBlock).where(
            FactsBlock.session_state_id == session_state_id,
            FactsBlock.key == key,
        )
        result = await self.session.execute(stmt)
        fact = result.scalars().first()
        if fact:
            fact.value = value
            await self.session.flush()
            return fact

        fact = FactsBlock(session_state_id=session_state_id, key=key, value=value)
        self.session.add(fact)
        await self.session.flush()
        return fact

    async def add_scratchpad(self, session_state_id: str, kind: str, content: dict) -> Scratchpad:
        scratch = Scratchpad(session_state_id=session_state_id, kind=kind, content=content)
        self.session.add(scratch)
        await self.session.flush()
        return scratch

    async def update_manifest(
        self,
        state: SessionState,
        *,
        current_phase: str,
        completed_steps: list,
        pending_steps: list,
        next_action: str | None,
    ) -> None:
        state.current_phase = current_phase
        state.completed_steps = completed_steps
        state.pending_steps = pending_steps
        state.next_action = next_action
        await self.session.flush()

