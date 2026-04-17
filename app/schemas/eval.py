from typing import List
import uuid
from pydantic import BaseModel


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
