import json
import re
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user, get_user_scoped_session
from backend.app.core.config import get_settings
from backend.app.db.models import Conversation, Feedback, Message, User
from backend.app.llm.generation import answer, token_stream, validate_citations
from backend.app.retrieval.hybrid import Hit, retrieve

router = APIRouter(prefix="/chat", tags=["chat"])


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=4000)
    conversation_id: uuid.UUID | None = None
    deep_search: bool = False


class FeedbackIn(BaseModel):
    value: str
    reason: str | None = Field(default=None, max_length=2000)


class CitationOut(BaseModel):
    id: str
    document_id: str
    title: str
    page_start: int | None
    page_end: int | None
    heading_path: list[str]
    snippet: str
    score: float
    url: str


def _citation(marker: int, hit: Hit) -> dict[str, object]:
    return {
        "marker": marker,
        "id": str(hit.chunk_id),
        "document_id": str(hit.document_id),
        "title": hit.title,
        "page_start": hit.page_start,
        "page_end": hit.page_end,
        "heading_path": hit.heading_path,
        "snippet": hit.text[:700],
        "score": hit.score,
        "url": hit.url,
    }


@router.post("/ask")
async def ask(
    payload: AskIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_scoped_session),
) -> StreamingResponse:
    redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        minute = datetime.now(UTC).strftime("%Y%m%d%H%M")
        key = f"chat-rate:{user.id}:{minute}"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, 70)
        if count > get_settings().chat_rate_limit_per_minute:
            raise HTTPException(429, "Chat rate limit reached; try again in a minute")
    finally:
        await redis.aclose()
    conversation: Conversation | None
    if payload.conversation_id:
        conversation = await session.scalar(
            select(Conversation).where(
                Conversation.id == payload.conversation_id,
                Conversation.user_id == user.id,
                Conversation.organization_id == user.organization_id,
            )
        )
        if conversation is None:
            raise HTTPException(404, "Conversation not found")
        prior = list(
            (
                await session.scalars(
                    select(Message)
                    .where(Message.conversation_id == conversation.id)
                    .order_by(Message.created_at.desc())
                    .limit(4)
                )
            ).all()
        )
        if prior and re.search(
            r"\b(it|they|them|that|those|this|these|there|what about)\b", payload.question, re.I
        ):
            context = " ".join(message.content for message in reversed(prior))[-1200:]
            standalone_query = (
                f"Earlier conversation: {context}\nFollow-up question: {payload.question}"
            )
        else:
            standalone_query = payload.question
    else:
        conversation = Conversation(
            user_id=user.id, organization_id=user.organization_id, title=payload.question[:80]
        )
        session.add(conversation)
        await session.flush()
        standalone_query = payload.question
    user_message = Message(conversation_id=conversation.id, role="user", content=payload.question)
    session.add(user_message)
    hits = await retrieve(session, user, standalone_query, 16 if payload.deep_search else None)
    generated = await answer(payload.question, hits)
    clean_answer, valid_citations = validate_citations(generated, hits)
    if hits and not valid_citations:
        clean_answer = (
            "I could not verify a sufficiently supported answer in the available source passages."
        )
    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=clean_answer,
        retrieved_chunk_ids=[str(hit.chunk_id) for hit in hits],
    )
    session.add(assistant_message)
    await session.commit()
    citations = [_citation(marker, hit) for marker, hit in valid_citations]

    async def events() -> AsyncIterator[str]:
        yield f"event: meta\ndata: {json.dumps({'conversation_id': str(conversation.id), 'message_id': str(assistant_message.id)})}\n\n"
        async for token in token_stream(clean_answer):
            yield f"event: token\ndata: {json.dumps({'text': token})}\n\n"
        yield f"event: citations\ndata: {json.dumps(citations)}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/conversations")
async def conversations(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_user_scoped_session)
) -> list[dict[str, str]]:
    rows = await session.scalars(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.created_at.desc())
    )
    return [
        {"id": str(row.id), "title": row.title, "created_at": row.created_at.isoformat()}
        for row in rows
    ]


@router.get("/conversations/{conversation_id}")
async def conversation_detail(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_scoped_session),
) -> dict[str, object]:
    conversation = await session.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user.id
        )
    )
    if conversation is None:
        raise HTTPException(404, "Conversation not found")
    rows = await session.scalars(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at)
    )
    return {
        "id": str(conversation.id),
        "title": conversation.title,
        "messages": [
            {
                "id": str(row.id),
                "role": row.role,
                "content": row.content,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ],
    }


@router.post("/messages/{message_id}/feedback")
async def feedback(
    message_id: uuid.UUID,
    payload: FeedbackIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_scoped_session),
) -> dict[str, str]:
    if payload.value not in {"up", "down"}:
        raise HTTPException(422, "value must be up or down")
    message = await session.scalar(
        select(Message)
        .join(Conversation)
        .where(Message.id == message_id, Conversation.user_id == user.id)
    )
    if message is None or message.role != "assistant":
        raise HTTPException(404, "Assistant message not found")
    existing = await session.scalar(select(Feedback).where(Feedback.message_id == message.id))
    if existing:
        existing.value, existing.reason = payload.value, payload.reason
    else:
        session.add(
            Feedback(
                message_id=message.id, user_id=user.id, value=payload.value, reason=payload.reason
            )
        )
    await session.commit()
    return {"status": "saved"}
