from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_db
from app.api.deps import get_current_user
from app.schemas.auth import UserContext
from app.schemas.knowledgebase import KBCreate, KBResponse
from app.models.knowledgebase import KnowledgeBase

router = APIRouter(prefix="/kbs", tags=["Knowledge Bases"])


@router.post("", response_model=KBResponse, status_code=201,
             summary="Create a knowledge base for this organisation")
async def create_kb(
    payload: KBCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    kb = KnowledgeBase(name=payload.name, org_id=current_user.org_id)
    db.add(kb)
    await db.flush()
    return kb


@router.get("", response_model=list[KBResponse],
            summary="List all knowledge bases for this organisation")
async def list_kbs(
    db: AsyncSession = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.org_id == current_user.org_id)
    )
    return result.scalars().all()


@router.get("/{kb_id}", response_model=KBResponse,
            summary="Get a single knowledge base by ID")
async def get_kb(
    kb_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.org_id == current_user.org_id,
        )
    )
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found.")
    return kb
