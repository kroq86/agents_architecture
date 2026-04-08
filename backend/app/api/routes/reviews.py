from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import verify_api_key
from app.core.schemas import HumanReviewItemRead, ReviewResolveRequest
from app.db.session import get_session
from app.observability.metrics import HITL_QUEUE_DEPTH
from app.services.repositories.runs import RunRepository

router = APIRouter()


@router.get("/reviews", response_model=list[HumanReviewItemRead])
async def list_reviews(
    status: str = Query(
        default="pending",
        description="Filter by status; use 'all' to include every status.",
    ),
    limit: int = Query(default=100, ge=1, le=500),
    _: None = Depends(verify_api_key),
    session: AsyncSession = Depends(get_session),
) -> list[HumanReviewItemRead]:
    repo = RunRepository(session)
    async with session.begin():
        items = await repo.list_review_items(status=status, limit=limit)
    return [HumanReviewItemRead.model_validate(i, from_attributes=True) for i in items]


@router.patch("/reviews/{item_id}", response_model=HumanReviewItemRead)
async def resolve_review(
    item_id: str,
    body: ReviewResolveRequest,
    _: None = Depends(verify_api_key),
    session: AsyncSession = Depends(get_session),
) -> HumanReviewItemRead:
    repo = RunRepository(session)
    async with session.begin():
        item = await repo.resolve_review_item(
            item_id,
            status=body.status,
            resolution=body.resolution,
            resolver=body.resolver,
        )
        if item is None:
            raise HTTPException(status_code=404, detail="Review item not found")
        pending = await repo.pending_review_count()
    HITL_QUEUE_DEPTH.set(pending)
    return HumanReviewItemRead.model_validate(item, from_attributes=True)
