from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_db
from app.api.deps import get_current_user
from app.schemas.auth import UserContext
from app.schemas.feedback import FeedbackCreate, FeedbackResponse
from app.models.feedback import Feedback
from app.models.message import Message
from app.models.chat import Chat

router = APIRouter(tags=["Feedback"])


@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    status_code=201,
    summary="Submit thumbs-up/down feedback on an assistant message",
)
async def submit_feedback(
    payload: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    # Verify the message exists and belongs to this org (via chat → org_id)
    result = await db.execute(
        select(Message)
        .join(Chat, Message.chat_id == Chat.id)
        .where(
            Message.id == payload.message_id,
            Chat.org_id == current_user.org_id,
        )
    )
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found.")

    feedback = Feedback(
        message_id=payload.message_id,
        rating=payload.rating,
        note=payload.note,
    )
    db.add(feedback)
    await db.flush()
    return feedback
