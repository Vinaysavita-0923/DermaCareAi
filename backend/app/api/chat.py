"""
POST   /api/v1/chat                 — send a message (start or continue a chat)
GET    /api/v1/chat/sessions        — list your conversations
GET    /api/v1/chat/sessions/{id}   — one conversation with its messages
DELETE /api/v1/chat/sessions/{id}   — delete a conversation

Ownership: a chat session is addressed by id in two of these routes, so
every one of them loads the session and calls ensure_owner() before
doing anything — a session belonging to another user returns 404,
identical to one that doesn't exist. The message list is always scoped
to the owned session, so there's no way to read another user's
messages.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import ensure_owner, get_current_user
from app.database.connection import get_db
from app.database.models import ChatSession, User
from app.schemas.chat_schema import (
    ActionConfirmRequest,
    ActionConfirmResponse,
    ChatSendRequest,
    ChatSendResponse,
    ChatSessionDetail,
    ChatSessionOut,
    ProposedActionOut,
    ToolTraceOut,
)
from app.services.agent_tools import ActionError, execute_action
from app.services.chat_service import process_agent_turn, process_user_turn
from app.services.llm_service import ProviderError, get_provider

router = APIRouter(prefix="/chat", tags=["chat"])
settings = get_settings()


def _get_owned_session(db: Session, session_id: int, user: User) -> ChatSession:
    session = db.get(ChatSession, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    ensure_owner(session.user_id, user)  # raises 404 if not the owner
    return session


@router.post("", response_model=ChatSendResponse)
def send_message(
    payload: ChatSendRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatSendResponse:
    # Resolve the session: either an existing one the caller owns, or a
    # brand-new one. A client supplying someone else's session_id gets a
    # 404 from _get_owned_session — it can't inject into another user's
    # conversation.
    if payload.session_id is not None:
        session = _get_owned_session(db, payload.session_id, current_user)
    else:
        session = ChatSession(
            user_id=current_user.id,
            title=payload.message[:60],  # a simple title from the first message
        )
        db.add(session)
        db.commit()
        db.refresh(session)

    outcome = None
    try:
        # Inside the try: a misconfigured cloud provider (e.g. LLM_PROVIDER=gemini
        # with no GEMINI_API_KEY) raises ProviderError here too, and gets the
        # same clean 503 as any other provider failure, not a generic 500.
        provider = get_provider(settings.llm_provider)
        if provider.supports_tools:
            assistant_msg, outcome = process_agent_turn(
                db=db,
                user=current_user,
                session=session,
                provider=provider,
                user_text=payload.message,
                use_profile=payload.use_profile,
            )
        else:
            assistant_msg = process_user_turn(
                db=db, session=session, provider=provider, user_text=payload.message
            )
    except ProviderError:
        # Clean, non-leaky error — no provider internals exposed.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The assistant is temporarily unavailable. Please try again.",
        )

    return ChatSendResponse(
        session_id=session.id,
        reply=assistant_msg,
        is_mock=assistant_msg.is_mock_response,
        tool_trace=[ToolTraceOut(tool=t.tool, label=t.label) for t in outcome.trace] if outcome else [],
        proposed_actions=(
            [ProposedActionOut(token=p.token, kind=p.kind, summary=p.summary) for p in outcome.proposals]
            if outcome
            else []
        ),
    )


@router.post("/actions/confirm", response_model=ActionConfirmResponse)
def confirm_action(
    payload: ActionConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ActionConfirmResponse:
    """The only place an agent-proposed action is actually carried out.
    The token is signed, bound to this user, short-lived and single-use."""
    try:
        message = execute_action(db, current_user, payload.token)
    except ActionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return ActionConfirmResponse(message=message)


@router.get("/sessions", response_model=list[ChatSessionOut])
def list_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChatSession]:
    return (
        db.query(ChatSession)
        .filter(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.created_at.desc())
        .all()
    )


@router.get("/sessions/{session_id}", response_model=ChatSessionDetail)
def get_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatSession:
    session = _get_owned_session(db, session_id, current_user)
    # messages relationship is ordered by insertion (id) naturally;
    # return them oldest-first for display.
    session.messages.sort(key=lambda m: m.id)
    return session


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    session = _get_owned_session(db, session_id, current_user)
    db.delete(session)  # cascades to messages (configured on the model)
    db.commit()
