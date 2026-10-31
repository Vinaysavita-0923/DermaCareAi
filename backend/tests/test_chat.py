"""
Tests for Phase 5: the chatbot.

Covers authentication, conversation ownership/isolation, message
persistence, provider failure handling, and the safety layer's
behavior.

NOTE ON SAFETY TESTING: the safety tests below prove the *rules fire as
written* — e.g. a message containing "fever" is blocked and the LLM is
not called. They do NOT and cannot prove the assistant is medically
safe in general. Keyword rules miss things. This is verification of a
guardrail, not a safety certification.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.connection import Base, get_db
from app.main import app

TEST_DB_PATH = "test_phase5_chat.db"
TEST_DB_URL = f"sqlite:///{TEST_DB_PATH}"

_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
_TestSessionLocal = sessionmaker(bind=_engine)


def _override_get_db():
    db = _TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=_engine)
    Base.metadata.create_all(bind=_engine)
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture(scope="module", autouse=True)
def cleanup_file():
    yield
    _engine.dispose()
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


client = TestClient(app)


def make_token(email: str) -> str:
    client.post(
        "/api/v1/auth/register",
        json={"full_name": email.split("@")[0], "email": email, "password": "StrongPass1"},
    )
    return client.post(
        "/api/v1/auth/login", json={"email": email, "password": "StrongPass1"}
    ).json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------
# Auth + validation
# ---------------------------------------------------------------------
def test_chat_requires_auth():
    assert client.post("/api/v1/chat", json={"message": "hi"}).status_code == 401
    assert client.get("/api/v1/chat/sessions").status_code == 401


def test_empty_message_rejected():
    token = make_token("c1@example.com")
    assert client.post("/api/v1/chat", headers=auth(token), json={"message": "   "}).status_code == 422


def test_overlong_message_rejected():
    token = make_token("c2@example.com")
    long_message = "a" * 5000
    resp = client.post("/api/v1/chat", headers=auth(token), json={"message": long_message})
    assert resp.status_code == 422


# ---------------------------------------------------------------------
# Basic send + persistence
# ---------------------------------------------------------------------
def test_send_creates_session_and_persists_both_messages():
    token = make_token("c3@example.com")
    resp = client.post("/api/v1/chat", headers=auth(token), json={"message": "How often should I cleanse?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_mock"] is True
    assert body["reply"]["role"] == "assistant"
    session_id = body["session_id"]

    # The conversation should now hold the user message + the reply.
    detail = client.get(f"/api/v1/chat/sessions/{session_id}", headers=auth(token)).json()
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["user", "assistant"]
    assert "cleanse" in detail["messages"][0]["content"].lower()


def test_continue_existing_session():
    token = make_token("c4@example.com")
    first = client.post("/api/v1/chat", headers=auth(token), json={"message": "Tell me about niacinamide"}).json()
    sid = first["session_id"]
    client.post("/api/v1/chat", headers=auth(token), json={"session_id": sid, "message": "and sunscreen?"})

    detail = client.get(f"/api/v1/chat/sessions/{sid}", headers=auth(token)).json()
    # 2 turns -> 4 messages.
    assert len(detail["messages"]) == 4


def test_assistant_answer_includes_disclaimer():
    token = make_token("c5@example.com")
    resp = client.post("/api/v1/chat", headers=auth(token), json={"message": "help with dry skin"})
    reply = resp.json()["reply"]["content"].lower()
    assert "not medical advice" in reply


# ---------------------------------------------------------------------
# Ownership / isolation
# ---------------------------------------------------------------------
def test_user_b_cannot_read_user_a_session():
    ta = make_token("chat_a@example.com")
    tb = make_token("chat_b@example.com")
    sid = client.post("/api/v1/chat", headers=auth(ta), json={"message": "A private chat"}).json()["session_id"]

    assert client.get(f"/api/v1/chat/sessions/{sid}", headers=auth(tb)).status_code == 404


def test_user_b_cannot_post_into_user_a_session():
    ta = make_token("chat_a2@example.com")
    tb = make_token("chat_b2@example.com")
    sid = client.post("/api/v1/chat", headers=auth(ta), json={"message": "A chat"}).json()["session_id"]

    resp = client.post("/api/v1/chat", headers=auth(tb), json={"session_id": sid, "message": "inject"})
    assert resp.status_code == 404


def test_user_b_cannot_delete_user_a_session():
    ta = make_token("chat_a3@example.com")
    tb = make_token("chat_b3@example.com")
    sid = client.post("/api/v1/chat", headers=auth(ta), json={"message": "A chat"}).json()["session_id"]

    assert client.delete(f"/api/v1/chat/sessions/{sid}", headers=auth(tb)).status_code == 404
    # still there for A
    assert client.get(f"/api/v1/chat/sessions/{sid}", headers=auth(ta)).status_code == 200


def test_session_list_only_shows_own():
    ta = make_token("chat_a4@example.com")
    tb = make_token("chat_b4@example.com")
    client.post("/api/v1/chat", headers=auth(ta), json={"message": "A chat"})

    assert client.get("/api/v1/chat/sessions", headers=auth(tb)).json() == []


def test_delete_removes_session_and_messages():
    token = make_token("c6@example.com")
    sid = client.post("/api/v1/chat", headers=auth(token), json={"message": "hello"}).json()["session_id"]
    assert client.delete(f"/api/v1/chat/sessions/{sid}", headers=auth(token)).status_code == 204
    assert client.get(f"/api/v1/chat/sessions/{sid}", headers=auth(token)).status_code == 404


# ---------------------------------------------------------------------
# Provider failure handling
# ---------------------------------------------------------------------
def test_provider_failure_returns_503_and_persists_nothing(monkeypatch):
    token = make_token("c7@example.com")

    from app.services.llm_service import LLMProvider, ProviderError

    class FailingProvider(LLMProvider):
        @property
        def is_mock(self) -> bool:
            return True

        def generate(self, *, user_message, history):
            raise ProviderError("simulated timeout")

    monkeypatch.setattr("app.api.chat.get_provider", lambda name: FailingProvider())

    resp = client.post("/api/v1/chat", headers=auth(token), json={"message": "hello there"})
    assert resp.status_code == 503
    # The failed turn must not have left a user message dangling with no
    # reply. A fresh session was created, but it should hold 0 messages.
    sessions = client.get("/api/v1/chat/sessions", headers=auth(token)).json()
    assert len(sessions) == 1
    detail = client.get(f"/api/v1/chat/sessions/{sessions[0]['id']}", headers=auth(token)).json()
    assert detail["messages"] == []


def test_unexpected_provider_exception_is_handled(monkeypatch):
    token = make_token("c8@example.com")
    from app.services.llm_service import LLMProvider

    class ExplodingProvider(LLMProvider):
        @property
        def is_mock(self) -> bool:
            return True

        def generate(self, *, user_message, history):
            raise RuntimeError("unexpected boom")

    monkeypatch.setattr("app.api.chat.get_provider", lambda name: ExplodingProvider())
    resp = client.post("/api/v1/chat", headers=auth(token), json={"message": "hello"})
    # A non-ProviderError is still turned into a clean 503, not a 500.
    assert resp.status_code == 503


# ---------------------------------------------------------------------
# Safety layer (verifies the rules fire — NOT a safety certification)
# ---------------------------------------------------------------------
def test_emergency_message_bypasses_llm_and_warns(monkeypatch):
    token = make_token("c9@example.com")

    # Make the provider explode if it's ever called — proving the
    # emergency path does NOT reach the LLM.
    from app.services.llm_service import LLMProvider

    class MustNotBeCalled(LLMProvider):
        @property
        def is_mock(self) -> bool:
            return True

        def generate(self, *, user_message, history):
            raise AssertionError("LLM must not be called for an emergency message")

    monkeypatch.setattr("app.api.chat.get_provider", lambda name: MustNotBeCalled())

    resp = client.post(
        "/api/v1/chat",
        headers=auth(token),
        json={"message": "my face is swelling and I have a high fever"},
    )
    assert resp.status_code == 200
    reply = resp.json()["reply"]["content"].lower()
    assert "medical" in reply or "doctor" in reply or "emergency" in reply


def test_crisis_message_routes_to_human_support(monkeypatch):
    token = make_token("c10@example.com")
    from app.services.llm_service import LLMProvider

    class MustNotBeCalled(LLMProvider):
        @property
        def is_mock(self) -> bool:
            return True

        def generate(self, *, user_message, history):
            raise AssertionError("LLM must not be called for a crisis message")

    monkeypatch.setattr("app.api.chat.get_provider", lambda name: MustNotBeCalled())

    resp = client.post(
        "/api/v1/chat", headers=auth(token), json={"message": "I want to hurt myself"}
    )
    assert resp.status_code == 200
    reply = resp.json()["reply"]["content"].lower()
    assert "helpline" in reply or "crisis" in reply or "support" in reply


def test_normal_message_is_not_blocked():
    token = make_token("c11@example.com")
    resp = client.post("/api/v1/chat", headers=auth(token), json={"message": "what is a good cleanser"})
    assert resp.status_code == 200
    # a normal educational answer, not the emergency text
    assert "emergency number" not in resp.json()["reply"]["content"].lower()
