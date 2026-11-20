"""Request/response shapes for the chat endpoints."""
from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.config import get_settings
from app.database.models import ChatRole

_settings = get_settings()


class ChatSendRequest(BaseModel):
    # If omitted, a new conversation is started.
    session_id: int | None = None
    message: str
    # User consent for the assistant to read their saved skin assessment.
    use_profile: bool = True

    @field_validator("message")
    @classmethod
    def _validate_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message must not be empty.")
        if len(value) > _settings.chat_message_max_chars:
            raise ValueError(
                f"Message must be {_settings.chat_message_max_chars} characters or fewer."
            )
        return value


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: ChatRole
    content: str
    is_mock_response: bool
    created_at: datetime.datetime


class ToolTraceOut(BaseModel):
    tool: str
    label: str


class ProposedActionOut(BaseModel):
    token: str  # signed, short-lived, single use; send back to confirm
    kind: str
    summary: str


class ChatSendResponse(BaseModel):
    session_id: int
    reply: ChatMessageOut
    # True when the answer came from the mock provider (or is a fixed
    # safety response), so the frontend can label it honestly.
    is_mock: bool
    # What the agent looked up (not persisted) and what it proposes the
    # user confirm. Empty for the mock provider and safety responses.
    tool_trace: list[ToolTraceOut] = []
    proposed_actions: list[ProposedActionOut] = []


class ActionConfirmRequest(BaseModel):
    token: str


class ActionConfirmResponse(BaseModel):
    message: str


class ChatSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None
    created_at: datetime.datetime


class ChatSessionDetail(ChatSessionOut):
    messages: list[ChatMessageOut]
