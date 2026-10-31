"""
Tests for the chat agent (tool calling + confirm-before-write).

The model is replaced by a scripted provider, so these prove OUR
guarantees — tool scoping, no write without confirmation, single-use
confirmation, safety bypass — not the quality of any real model.
"""
from __future__ import annotations

import datetime
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.connection import Base, get_db
from app.database.models import Product
from app.main import app
from app.services.llm_service import AgentStep, LLMProvider, ProviderError, ToolCall

TEST_DB_PATH = "test_agent.db"
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


class ScriptedProvider(LLMProvider):
    """Plays back a fixed list of AgentSteps and records what it saw."""

    supports_tools = True

    def __init__(self, steps: list[AgentStep]):
        self._steps = list(steps)
        self.seen_tool_results: list[str] = []
        self.calls = 0

    @property
    def is_mock(self) -> bool:
        return False

    def chat(self, *, messages, tools):
        self.calls += 1
        self.seen_tool_results += [m["content"] for m in messages if m["role"] == "tool"]
        if not tools:  # like a real model: with no tools offered, it just answers
            return AgentStep("final answer", [])
        return self._steps.pop(0) if self._steps else AgentStep("done", [])

    def generate(self, *, user_message, history):  # pragma: no cover
        raise AssertionError("agent path must use chat(), not generate()")


def use(monkeypatch, provider):
    monkeypatch.setattr("app.api.chat.get_provider", lambda name: provider)


def say(token, text, session_id=None):
    return client.post(
        "/api/v1/chat", json={"message": text, "session_id": session_id}, headers=auth(token)
    )


def add_journal(token, note):
    r = client.post(
        "/api/v1/journal",
        json={"entry_date": datetime.date.today().isoformat(), "notes": note, "skin_feeling_tags": ["dry"]},
        headers=auth(token),
    )
    assert r.status_code == 201, r.text


# ---------------------------------------------------------------------
def test_agent_reads_only_the_callers_own_journal(monkeypatch):
    alice, bob = make_token("alice@example.com"), make_token("bob@example.com")
    add_journal(alice, "ALICE-SECRET-NOTE")
    add_journal(bob, "BOB-SECRET-NOTE")

    prov = ScriptedProvider(
        [AgentStep("", [ToolCall("get_recent_journal", {"limit": 5})]), AgentStep("You felt dry.", [])]
    )
    use(monkeypatch, prov)
    r = say(alice, "How has my skin been?")

    assert r.status_code == 200, r.text
    body = r.json()
    assert "You felt dry." in body["reply"]["content"]
    assert body["tool_trace"] == [{"tool": "get_recent_journal", "label": "Read your recent journal entries"}]
    joined = " ".join(prov.seen_tool_results)
    assert "ALICE-SECRET-NOTE" in joined
    assert "BOB-SECRET-NOTE" not in joined


def test_model_cannot_pick_another_user_via_arguments(monkeypatch):
    alice, bob = make_token("alice@example.com"), make_token("bob@example.com")
    add_journal(bob, "BOB-SECRET-NOTE")
    prov = ScriptedProvider(
        [AgentStep("", [ToolCall("get_recent_journal", {"user_id": 2, "limit": 5})]), AgentStep("ok", [])]
    )
    use(monkeypatch, prov)
    say(alice, "show me bob's journal")
    assert "BOB-SECRET-NOTE" not in " ".join(prov.seen_tool_results)


def test_unknown_tool_and_bad_arguments_do_not_crash(monkeypatch):
    t = make_token("a@example.com")
    prov = ScriptedProvider(
        [
            AgentStep("", [ToolCall("delete_everything", {}), ToolCall("get_product_details", {"wrong": 1})]),
            AgentStep("fine", []),
        ]
    )
    use(monkeypatch, prov)
    r = say(t, "hi")
    assert r.status_code == 200
    assert any("Unknown tool" in x for x in prov.seen_tool_results)


def test_agent_stops_after_max_steps_and_still_answers(monkeypatch):
    t = make_token("a@example.com")
    loop = [AgentStep("", [ToolCall("get_my_routines", {"n": i})]) for i in range(20)]
    prov = ScriptedProvider(loop + [AgentStep("final answer", [])])
    use(monkeypatch, prov)
    r = say(t, "hi")
    assert r.status_code == 200
    assert prov.calls <= 6  # max steps + the final no-tools call


def test_propose_does_not_write_and_confirm_does(monkeypatch):
    t = make_token("a@example.com")
    prov = ScriptedProvider(
        [
            AgentStep("", [ToolCall("propose_create_routine", {"routine_type": "morning", "steps": [{"notes": "cleanse"}]})]),
            AgentStep("Press Confirm to save it.", []),
        ]
    )
    use(monkeypatch, prov)
    r = say(t, "make me a morning routine").json()

    assert len(r["proposed_actions"]) == 1
    assert client.get("/api/v1/routines", headers=auth(t)).json() == []  # nothing saved yet

    token = r["proposed_actions"][0]["token"]
    c = client.post("/api/v1/chat/actions/confirm", json={"token": token}, headers=auth(t))
    assert c.status_code == 200, c.text
    routines = client.get("/api/v1/routines", headers=auth(t)).json()
    assert len(routines) == 1 and routines[0]["routine_type"] == "morning"

    # single use: replaying the same token must not create a second routine
    again = client.post("/api/v1/chat/actions/confirm", json={"token": token}, headers=auth(t))
    assert again.status_code == 400
    assert len(client.get("/api/v1/routines", headers=auth(t)).json()) == 1


def test_confirm_rejects_other_users_tampered_and_login_tokens(monkeypatch):
    alice, bob = make_token("alice@example.com"), make_token("bob@example.com")
    prov = ScriptedProvider(
        [AgentStep("", [ToolCall("propose_create_routine", {"routine_type": "night"})]), AgentStep("ok", [])]
    )
    use(monkeypatch, prov)
    token = say(alice, "night routine").json()["proposed_actions"][0]["token"]

    assert client.post("/api/v1/chat/actions/confirm", json={"token": token}, headers=auth(bob)).status_code == 400
    assert client.post("/api/v1/chat/actions/confirm", json={"token": token + "x"}, headers=auth(alice)).status_code == 400
    # a normal login token is not an action token
    assert client.post("/api/v1/chat/actions/confirm", json={"token": alice}, headers=auth(alice)).status_code == 400
    assert client.get("/api/v1/routines", headers=auth(alice)).json() == []
    assert client.get("/api/v1/routines", headers=auth(bob)).json() == []
    assert client.post("/api/v1/chat/actions/confirm", json={"token": token}).status_code == 401


def test_cannot_propose_logging_someone_elses_routine(monkeypatch):
    alice, bob = make_token("alice@example.com"), make_token("bob@example.com")
    rid = client.post("/api/v1/routines", json={"routine_type": "morning", "items": []}, headers=auth(alice)).json()["id"]
    prov = ScriptedProvider(
        [AgentStep("", [ToolCall("propose_log_routine", {"routine_id": rid})]), AgentStep("ok", [])]
    )
    use(monkeypatch, prov)
    r = say(bob, "log it").json()
    assert r["proposed_actions"] == []
    assert any("No routine" in x for x in prov.seen_tool_results)


def test_log_routine_proposal_flow(monkeypatch):
    t = make_token("a@example.com")
    rid = client.post("/api/v1/routines", json={"routine_type": "morning", "items": []}, headers=auth(t)).json()["id"]
    prov = ScriptedProvider(
        [AgentStep("", [ToolCall("propose_log_routine", {"routine_id": rid, "completed": True})]), AgentStep("Confirm?", [])]
    )
    use(monkeypatch, prov)
    action = say(t, "I did my routine").json()["proposed_actions"][0]
    assert client.post("/api/v1/chat/actions/confirm", json={"token": action["token"]}, headers=auth(t)).status_code == 200
    rep = client.get("/api/v1/reports/summary?days=7", headers=auth(t)).json()
    assert rep["routine_completion"][0]["days_completed"] == 1


def test_product_details_include_precautions(monkeypatch):
    t = make_token("a@example.com")
    db = _TestSessionLocal()
    from app.database.models import Ingredient, ProductIngredient

    p = Product(name="Test Serum", is_sample_data=True)
    ing = Ingredient(name="Retinol", precautions="Avoid in pregnancy; use sunscreen.")
    db.add_all([p, ing])
    db.flush()
    db.add(ProductIngredient(product_id=p.id, ingredient_id=ing.id))
    db.commit()
    pid = p.id
    db.close()

    prov = ScriptedProvider(
        [AgentStep("", [ToolCall("get_product_details", {"product_id": pid})]), AgentStep("Note the precaution.", [])]
    )
    use(monkeypatch, prov)
    assert say(t, "is Test Serum ok?").status_code == 200
    assert any("Avoid in pregnancy" in x for x in prov.seen_tool_results)


def test_safety_rule_bypasses_agent_entirely(monkeypatch):
    t = make_token("a@example.com")

    class MustNotBeCalled(ScriptedProvider):
        def chat(self, *, messages, tools):
            raise AssertionError("model must not be called for an emergency message")

    use(monkeypatch, MustNotBeCalled([]))
    r = say(t, "my face is swelling and I have a fever")
    assert r.status_code == 200
    assert r.json()["tool_trace"] == [] and r.json()["proposed_actions"] == []


def test_provider_failure_returns_503_and_saves_nothing(monkeypatch):
    t = make_token("a@example.com")

    class Down(ScriptedProvider):
        def chat(self, *, messages, tools):
            raise ProviderError("down")

    use(monkeypatch, Down([]))
    assert say(t, "hello").status_code == 503
    assert client.get("/api/v1/chat/sessions", headers=auth(t)).json()[0]["id"]  # session row only
    sid = client.get("/api/v1/chat/sessions", headers=auth(t)).json()[0]["id"]
    assert client.get(f"/api/v1/chat/sessions/{sid}", headers=auth(t)).json()["messages"] == []
