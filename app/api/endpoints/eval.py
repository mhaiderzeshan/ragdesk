from typing import List
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db import get_db
from app.api.deps import get_current_user
from app.schemas.auth import UserContext
from app.api.rbac import require_role
from app.services.retrieval import search_similar_chunks
from app.services.chat import _embed_query
from app.core.rate_limit import limiter
from app.services.audit import log_action

router = APIRouter(tags=["Evaluation"])


class EvalItem(BaseModel):
    question: str
    expected_document_ids: List[str]


class EvalRunRequest(BaseModel):
    kb_id: uuid.UUID
    dataset: List[EvalItem]
    top_k: int = 6


class EvalResultItem(BaseModel):
    question: str
    hit: bool
    rr: float  # Reciprocal Rank


class EvalRunResponse(BaseModel):
    total_questions: int
    hit_rate: float
    mrr: float
    results: List[EvalResultItem]


@router.post(
    "/eval/run",
    response_model=EvalRunResponse,
    summary="Batch evaluation runner for evaluating retrieval quality (admin only).",
)
@limiter.limit("2/minute")
async def run_evaluation(
    request: Request,
    payload: EvalRunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserContext = Depends(require_role("admin")),
):
    """
    Run retrieval for a dataset of questions and measure Hit Rate and Mean Reciprocal Rank (MRR).
    This measures if the expected documents are successfully retrieved in the top K.
    """
    if not payload.dataset:
        raise HTTPException(status_code=400, detail="Dataset cannot be empty")

    results = []
    hits = 0
    sum_rr = 0.0

    for item in payload.dataset:
        try:
            # 1. Embed query
            query_embedding = _embed_query(item.question)
            
            # 2. Retrieve chunks
            chunks = await search_similar_chunks(
                db=db,
                kb_id=payload.kb_id,
                org_id=current_user.org_id,
                query_embedding=query_embedding,
                top_k=payload.top_k,
            )
            
            # Extract unique document IDs from retrieved chunks (preserving order of first appearance)
            retrieved_doc_ids = []
            for c in chunks:
                doc_id = c["document_id"]
                if doc_id not in retrieved_doc_ids:
                    retrieved_doc_ids.append(doc_id)
            
            # 3. Calculate metrics for this query
            hit = False
            rr = 0.0
            for rank, ret_doc_id in enumerate(retrieved_doc_ids, start=1):
                if ret_doc_id in item.expected_document_ids:
                    hit = True
                    rr = 1.0 / rank
                    break  # We found the first relevant document
            
            if hit:
                hits += 1
            sum_rr += rr
            
            results.append(EvalResultItem(
                question=item.question,
                hit=hit,
                rr=rr,
            ))
            
        except Exception as e:
            # Depending on how strict the eval should be, we could skip or fail.
            # Here we just mark as zero for this item.
            results.append(EvalResultItem(
                question=item.question,
                hit=False,
                rr=0.0
            ))

    total = len(payload.dataset)
    hit_rate = hits / total
    mrr = sum_rr / total

    # Log this evaluation run
    await log_action(
        db, current_user.org_id, current_user.user_id, 
        "eval_run", str(payload.kb_id), 
        {"hit_rate": hit_rate, "mrr": mrr}
    )

    return EvalRunResponse(
        total_questions=total,
        hit_rate=hit_rate,
        mrr=mrr,
        results=results,
    )
