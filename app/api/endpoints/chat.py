"""
Chat endpoints:
  POST /chat           — non-streaming answer with citations
  POST /chat/stream    — SSE streaming answer with citations in final event
  GET  /chats/{id}     — conversation history
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.api.deps import get_current_user
from app.schemas.auth import UserContext
from app.schemas.chat import ChatRequest, ChatResponse, ChatHistoryResponse
from app.models.chat import Chat
from app.services.chat import generate_answer, generate_answer_stream
from app.services.audit import log_action

# To avoid circular imports, you can import limiter locally or pass it via dependency.
# A simpler way is to import from app.main but that can cause circularity. 
# Alternatively, instantiate it here or in deps.
from app.core.rate_limit import limiter

router = APIRouter(tags=["Chat"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Non-streaming answer with citations",
)
@limiter.limit("20/minute")
async def chat(
    request: Request,
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    try:
        response = await generate_answer(
            db=db,
            kb_id=payload.kb_id,
            org_id=current_user.org_id,
            user_id=current_user.user_id,
            message=payload.message,
            chat_id=payload.chat_id,
            top_k=payload.top_k,
        )
        # Log this action
        await log_action(db, current_user.org_id, current_user.user_id, "chat", str(payload.kb_id))
        return response
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


@router.post(
    "/chat/stream",
    summary="Server-Sent Events streaming answer with citations in final event",
    response_class=StreamingResponse,
)
@limiter.limit("20/minute")
async def chat_stream(
    request: Request,
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    """
    Streams tokens as SSE events.
    Format:
        data: <token>\n\n           (one per token)
        data: {"event":"citations", ...}\n\n  (final event)
        data: [DONE]\n\n

    Budget latency tip: retrieval runs first (fast), then streaming starts.
    """
    try:
        stream = generate_answer_stream(
            db=db,
            kb_id=payload.kb_id,
            org_id=current_user.org_id,
            user_id=current_user.user_id,
            message=payload.message,
            chat_id=payload.chat_id,
            top_k=payload.top_k,
        )
        return StreamingResponse(
            stream,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",  # disable Nginx buffering
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/chats/{chat_id}",
    response_model=ChatHistoryResponse,
    summary="Get conversation history for a chat session",
)
async def get_chat_history(
    chat_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    result = await db.execute(
        select(Chat)
        .where(Chat.id == chat_id, Chat.org_id == current_user.org_id)
        .options(selectinload(Chat.messages))
    )
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found.")
    return ChatHistoryResponse.model_validate(chat)
