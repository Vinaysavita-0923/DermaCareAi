"""
Tests for the Gemini / Groq cloud providers and the fallback chain.

Gemini and Groq are tested by monkeypatching their SDK client classes with
fakes that return canned, real-shaped responses — nothing here makes a
network call or needs a real API key. This proves our request-building
and response-parsing code is correct for the shapes each SDK actually
uses; it cannot prove the live APIs behave exactly as documented.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.config import get_settings
from app.services.llm_service import (
    AgentStep,
    ChainedProvider,
    GeminiProvider,
    GroqProvider,
    LLMProvider,
    ProviderError,
    ToolCall,
    _build_single_provider,
    _to_gemini_contents,
    _to_openai_messages,
    get_provider,
)


# ---------------------------------------------------------------------
# Construction: a cloud provider with no key is a clean ProviderError
# ---------------------------------------------------------------------
def test_gemini_without_key_raises_provider_error(monkeypatch):
    monkeypatch.setattr(get_settings(), "gemini_api_key", None)
    with pytest.raises(ProviderError):
        GeminiProvider()


def test_groq_without_key_raises_provider_error(monkeypatch):
    monkeypatch.setattr(get_settings(), "groq_api_key", None)
    with pytest.raises(ProviderError):
        GroqProvider()


def test_unknown_provider_name_is_a_hard_error():
    with pytest.raises(ValueError):
        _build_single_provider("chatgpt")


# ---------------------------------------------------------------------
# Message/tool translation helpers
# ---------------------------------------------------------------------
def test_openai_message_translation_pairs_tool_call_ids_in_order():
    internal = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"function": {"name": "a", "arguments": {"x": 1}}},
                {"function": {"name": "b", "arguments": {}}},
            ],
        },
        {"role": "tool", "tool_name": "a", "content": '{"ok": true}'},
        {"role": "tool", "tool_name": "b", "content": '{"ok": false}'},
    ]
    wire = _to_openai_messages(internal)
    assert wire[0] == {"role": "system", "content": "sys"}
    calls = wire[2]["tool_calls"]
    assert [c["function"]["name"] for c in calls] == ["a", "b"]
    assert wire[3]["tool_call_id"] == calls[0]["id"]
    assert wire[4]["tool_call_id"] == calls[1]["id"]
    assert wire[3]["content"] == '{"ok": true}'


def test_gemini_content_translation_maps_roles_and_pulls_out_system():
    internal = [
        {"role": "system", "content": "be nice"},
        {"role": "user", "content": "hello"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {"name": "get_x", "arguments": {"a": 1}}}],
        },
        {"role": "tool", "tool_name": "get_x", "content": '{"a": 1}'},
        {"role": "assistant", "content": "done"},
    ]
    system, contents = _to_gemini_contents(internal)
    assert system == "be nice"
    roles = [c.role for c in contents]
    assert roles == ["user", "model", "user", "model"]
    assert contents[1].parts[0].function_call.name == "get_x"
    assert contents[2].parts[0].function_response.name == "get_x"


# ---------------------------------------------------------------------
# GeminiProvider.chat() against a faked SDK client
# ---------------------------------------------------------------------
def _fake_gemini_response(*, text: str | None = None, call: tuple[str, dict] | None = None):
    parts = []
    if text is not None:
        parts.append(SimpleNamespace(text=text, function_call=None))
    if call is not None:
        name, args = call
        parts.append(SimpleNamespace(text=None, function_call=SimpleNamespace(name=name, args=args)))
    return SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=parts))])


def test_gemini_chat_parses_text_and_tool_calls(monkeypatch):
    monkeypatch.setattr(get_settings(), "gemini_api_key", "fake-key")
    provider = GeminiProvider()

    captured = {}

    class FakeModels:
        def generate_content(self, *, model, contents, config):
            captured["model"] = model
            captured["contents"] = contents
            captured["config"] = config
            return _fake_gemini_response(call=("get_my_profile", {"n": 1}))

    monkeypatch.setattr(provider, "_client", SimpleNamespace(models=FakeModels()))
    step = provider.chat(messages=[{"role": "user", "content": "hi"}], tools=[])
    assert isinstance(step, AgentStep)
    assert step.tool_calls == [ToolCall(name="get_my_profile", arguments={"n": 1})]
    assert captured["model"] == provider._model


def test_gemini_chat_wraps_sdk_errors_as_provider_error(monkeypatch):
    monkeypatch.setattr(get_settings(), "gemini_api_key", "fake-key")
    provider = GeminiProvider()

    class Boom:
        def generate_content(self, **kw):
            raise RuntimeError("network down")

    monkeypatch.setattr(provider, "_client", SimpleNamespace(models=Boom()))
    with pytest.raises(ProviderError):
        provider.chat(messages=[{"role": "user", "content": "hi"}], tools=[])


# ---------------------------------------------------------------------
# GroqProvider.chat() against a faked SDK client
# ---------------------------------------------------------------------
def _fake_groq_response(*, content: str | None = None, tool_calls=None):
    msg = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def test_groq_chat_parses_text_and_tool_calls(monkeypatch):
    monkeypatch.setattr(get_settings(), "groq_api_key", "fake-key")
    provider = GroqProvider()

    tc = SimpleNamespace(id="call_0", function=SimpleNamespace(name="search_products", arguments='{"query": "serum"}'))
    captured = {}

    class FakeCompletions:
        def create(self, **kw):
            captured.update(kw)
            return _fake_groq_response(content="", tool_calls=[tc])

    monkeypatch.setattr(provider, "_client", SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions())))
    step = provider.chat(messages=[{"role": "user", "content": "hi"}], tools=[])
    assert step.tool_calls == [ToolCall(name="search_products", arguments={"query": "serum"})]
    assert captured["model"] == provider._model


def test_groq_chat_handles_plain_text_reply(monkeypatch):
    monkeypatch.setattr(get_settings(), "groq_api_key", "fake-key")
    provider = GroqProvider()

    class FakeCompletions:
        def create(self, **kw):
            return _fake_groq_response(content="Use a gentle cleanser.", tool_calls=None)

    monkeypatch.setattr(provider, "_client", SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions())))
    step = provider.chat(messages=[{"role": "user", "content": "hi"}], tools=[])
    assert step.content == "Use a gentle cleanser." and step.tool_calls == []


def test_groq_chat_wraps_sdk_errors_as_provider_error(monkeypatch):
    monkeypatch.setattr(get_settings(), "groq_api_key", "fake-key")
    provider = GroqProvider()

    class Boom:
        def create(self, **kw):
            raise RuntimeError("rate limited")

    monkeypatch.setattr(provider, "_client", SimpleNamespace(chat=SimpleNamespace(completions=Boom())))
    with pytest.raises(ProviderError):
        provider.chat(messages=[{"role": "user", "content": "hi"}], tools=[])


# ---------------------------------------------------------------------
# ChainedProvider
# ---------------------------------------------------------------------
class _Scripted(LLMProvider):
    supports_tools = True

    def __init__(self, *, fails=False, content="ok", is_mock=False):
        self._fails = fails
        self._content = content
        self._is_mock = is_mock
        self.calls = 0

    @property
    def is_mock(self):
        return self._is_mock

    def chat(self, *, messages, tools):
        self.calls += 1
        if self._fails:
            raise ProviderError("boom")
        return AgentStep(content=self._content, tool_calls=[])

    def generate(self, *, user_message, history):  # pragma: no cover
        raise AssertionError("not used in these tests")


def test_chain_falls_through_to_the_next_provider_on_failure():
    first = _Scripted(fails=True)
    second = _Scripted(content="from second")
    chain = ChainedProvider([first, second])
    step = chain.chat(messages=[{"role": "user", "content": "hi"}], tools=[])
    assert step.content == "from second" and chain.is_mock is False
    assert first.calls == 1 and second.calls == 1


def test_chain_falls_back_to_mock_when_everything_fails():
    chain = ChainedProvider([_Scripted(fails=True), _Scripted(fails=True)])
    step = chain.chat(messages=[{"role": "user", "content": "what is niacinamide"}], tools=[])
    assert chain.is_mock is True
    assert "temporarily unavailable" in step.content
    assert "niacinamide" in step.content.lower() or len(step.content) > 0  # mock produced *something*


def test_chain_skips_members_that_cannot_chat():
    from app.services.llm_service import MockProvider

    chain = ChainedProvider([MockProvider(), _Scripted(content="second")])
    step = chain.chat(messages=[{"role": "user", "content": "hi"}], tools=[])
    assert step.content == "second"  # MockProvider.supports_tools is False -> skipped, not crashed


# ---------------------------------------------------------------------
# get_provider(): chain assembly from settings, unconfigured members skipped
# ---------------------------------------------------------------------
def test_get_provider_builds_chain_and_skips_unconfigured_fallback(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "llm_fallback_chain", "groq")
    monkeypatch.setattr(s, "groq_api_key", None)  # fallback not configured -> skipped
    provider = get_provider("mock")
    assert isinstance(provider, ChainedProvider)
    assert len(provider._providers) == 1  # just the primary "mock"; groq was skipped


def test_get_provider_chain_includes_a_configured_fallback(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "llm_fallback_chain", "groq")
    monkeypatch.setattr(s, "groq_api_key", "fake-key")
    provider = get_provider("mock")
    assert isinstance(provider, ChainedProvider)
    assert len(provider._providers) == 2
    assert isinstance(provider._providers[1], GroqProvider)


def test_get_provider_with_no_chain_setting_returns_the_plain_provider(monkeypatch):
    monkeypatch.setattr(get_settings(), "llm_fallback_chain", None)
    assert type(get_provider("mock")).__name__ == "MockProvider"


def test_get_provider_primary_misconfigured_cloud_provider_raises(monkeypatch):
    monkeypatch.setattr(get_settings(), "gemini_api_key", None)
    monkeypatch.setattr(get_settings(), "llm_fallback_chain", None)
    with pytest.raises(ProviderError):
        get_provider("gemini")


def _rate_limit_error():
    import httpx
    from groq import RateLimitError

    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    return RateLimitError("429", response=httpx.Response(429, request=request), body=None)


def test_groq_chat_moves_to_next_model_when_rate_limited(monkeypatch):
    monkeypatch.setattr(get_settings(), "groq_api_key", "fake-key")
    monkeypatch.setattr(get_settings(), "groq_fallback_models", "backup-a,backup-b")
    provider = GroqProvider()
    tried = []

    class FakeCompletions:
        def create(self, **kw):
            tried.append(kw["model"])
            if kw["model"] != "backup-b":
                raise _rate_limit_error()
            return _fake_groq_response(content="<think>plan</think>Use SPF daily.", tool_calls=None)

    monkeypatch.setattr(provider, "_client", SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions())))
    step = provider.chat(messages=[{"role": "user", "content": "hi"}], tools=[])
    assert tried == [provider._model, "backup-a", "backup-b"]
    assert step.content == "Use SPF daily."


def test_groq_chat_raises_when_every_model_is_rate_limited(monkeypatch):
    monkeypatch.setattr(get_settings(), "groq_api_key", "fake-key")
    monkeypatch.setattr(get_settings(), "groq_fallback_models", "backup-a")
    provider = GroqProvider()

    class Busy:
        def create(self, **kw):
            raise _rate_limit_error()

    monkeypatch.setattr(provider, "_client", SimpleNamespace(chat=SimpleNamespace(completions=Busy())))
    with pytest.raises(ProviderError):
        provider.chat(messages=[{"role": "user", "content": "hi"}], tools=[])
