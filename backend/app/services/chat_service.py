"""
Chat orchestration — the piece that ties safety, the provider, and
persistence together for one chat turn.

Order of operations for a user message (this order is deliberate):
  1. Safety screen the user's message FIRST. If it trips an emergency
     or crisis rule, we persist the user message + a fixed safe reply
     and return — the LLM is never called for a high-risk message.
  2. Otherwise, build trimmed history and call the provider.
  3. On provider failure, nothing partial is saved as an assistant
     answer; the caller turns the raised error into a clean 503.
  4. Append the standing medical disclaimer to a normal answer.
  5. Persist the user message and the assistant message together.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.models import ChatMessage, ChatRole, ChatSession, User
from app.services.agent_service import AgentOutcome, run_agent
from app.services.agent_tools import ToolContext
from app.services.llm_service import LLMProvider, ProviderError
from app.services.safety_service import append_disclaimer, screen_user_message

logger = logging.getLogger("skincare_api.chat")
settings = get_settings()


def _history_for_provider(db: Session, session_id: int) -> list[dict]:
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .all()
    )
    trimmed = rows[-settings.chat_history_limit :]
    return [{"role": m.role.value, "content": m.content} for m in trimmed]


def process_agent_turn(
    *,
    db: Session,
    user: User,
    session: ChatSession,
    provider: LLMProvider,
    user_text: str,
    use_profile: bool = True,
) -> tuple[ChatMessage, AgentOutcome | None]:
    """Same contract as process_user_turn, but the provider may use
    tools. Returns the persisted assistant message plus the agent's
    outcome (trace + proposed actions), or None when the safety layer
    answered without calling the model."""
    verdict = screen_user_message(user_text)
    if verdict.is_blocked:
        # Reuse the existing blocked-message path; the model and every
        # tool are skipped entirely.
        return process_user_turn(db=db, session=session, provider=provider, user_text=user_text), None

    history = _history_for_provider(db, session.id)
    ctx = ToolContext(db=db, user=user, use_profile=use_profile)
    try:
        outcome = run_agent(ctx=ctx, provider=provider, history=history, user_text=user_text)
    except ProviderError:
        logger.warning("Agent provider failed for session %s", session.id)
        raise
    except Exception as exc:
        logger.exception("Unexpected agent error for session %s", session.id)
        raise ProviderError(str(exc)) from exc

    user_msg = ChatMessage(session_id=session.id, role=ChatRole.user, content=user_text)
    assistant_msg = ChatMessage(
        session_id=session.id,
        role=ChatRole.assistant,
        content=append_disclaimer(outcome.content),
        is_mock_response=outcome.is_mock,
    )
    db.add_all([user_msg, assistant_msg])
    db.commit()
    db.refresh(assistant_msg)
    return assistant_msg, outcome


def process_user_turn(
    *,
    db: Session,
    session: ChatSession,
    provider: LLMProvider,
    user_text: str,
) -> ChatMessage:
    """Runs one full turn and returns the persisted assistant message.
    Raises ProviderError if the provider fails (caller handles it); in
    that case the user message is NOT left orphaned without a reply —
    nothing is committed at all, so the turn can be retried cleanly."""

    # 1. Safety screen first — a high-risk message never reaches the LLM.
    verdict = screen_user_message(user_text)
    if verdict.is_blocked:
        user_msg = ChatMessage(session_id=session.id, role=ChatRole.user, content=user_text)
        assistant_msg = ChatMessage(
            session_id=session.id,
            role=ChatRole.assistant,
            content=verdict.message or "",
            is_mock_response=True,  # a fixed safe response, not a model output
        )
        db.add_all([user_msg, assistant_msg])
        db.commit()
        db.refresh(assistant_msg)
        logger.info(
            "Safety rule triggered (category=%s) in session %s", verdict.category, session.id
        )
        return assistant_msg

    # 2. Build history and call the provider.
    history = _history_for_provider(db, session.id)
    try:
        result = provider.generate(user_message=user_text, history=history)
    except ProviderError:
        # Don't persist anything — a failed turn leaves the conversation
        # exactly as it was, so the client can retry without a dangling
        # user message that never got an answer.
        logger.warning("Provider failed for session %s", session.id)
        raise
    except Exception as exc:  # defense in depth: a provider raising
        # something unexpected is still a provider failure to us.
        logger.exception("Unexpected provider error for session %s", session.id)
        raise ProviderError(str(exc)) from exc

    answer = append_disclaimer(result.content)

    # 5. Persist both messages together.
    user_msg = ChatMessage(session_id=session.id, role=ChatRole.user, content=user_text)
    assistant_msg = ChatMessage(
        session_id=session.id,
        role=ChatRole.assistant,
        content=answer,
        is_mock_response=result.is_mock,
    )
    db.add_all([user_msg, assistant_msg])
    db.commit()
    db.refresh(assistant_msg)
    return assistant_msg
