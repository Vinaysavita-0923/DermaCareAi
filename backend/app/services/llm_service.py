"""
Provider-agnostic LLM interface.

The rest of the app never talks to a specific AI vendor — it talks to
`LLMProvider`. Today the only implementation is `MockProvider`, which
answers from the curated knowledge base with no network call and no API
key. A real hosted provider can be added later as another class
implementing the same `generate()` method, selected by the LLM_PROVIDER
env var, with its key read from the environment — without changing any
endpoint code.

No API key is required to run or test the backend today, by design.
"""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from app.services.safety_service import SYSTEM_INSTRUCTION

_KB_PATH = Path(__file__).resolve().parents[1] / "knowledge_base" / "skincare_faqs.json"


class ProviderError(Exception):
    """Raised for any provider-side failure (timeout, bad response,
    upstream error). The chat endpoint catches this and returns a clean
    503 instead of leaking provider internals."""


@dataclass
class LLMResult:
    content: str
    is_mock: bool
    source: str | None = None  # KB source attribution, when applicable


@dataclass
class ToolCall:
    name: str
    arguments: dict


@dataclass
class AgentStep:
    """One model response in an agent loop: either final text, or a set
    of tool calls it wants run before it continues."""

    content: str
    tool_calls: list[ToolCall]


class LLMProvider(ABC):
    # Providers that can request tool calls override this and chat().
    supports_tools: bool = False

    def chat(self, *, messages: list[dict], tools: list[dict]) -> AgentStep:
        raise NotImplementedError

    @property
    @abstractmethod
    def is_mock(self) -> bool: ...

    @abstractmethod
    def generate(self, *, user_message: str, history: list[dict]) -> LLMResult:
        """Return an assistant reply. `history` is a list of
        {"role": ..., "content": ...} dicts (oldest first), already
        trimmed by the caller. Must raise ProviderError on failure, not
        return a half-broken result."""
        ...


def _load_kb() -> list[dict]:
    try:
        data = json.loads(_KB_PATH.read_text(encoding="utf-8"))
        return data.get("entries", [])
    except (OSError, json.JSONDecodeError):
        # A missing/corrupt KB must not crash chat — the mock just falls
        # back to a generic educational answer.
        return []


class MockProvider(LLMProvider):
    """Deterministic, offline provider for development and tests.

    It does simple keyword retrieval against the curated knowledge base
    and returns the matching educational answer (with its source). If
    nothing matches, it returns a safe, generic educational response.
    It never invents medical claims — it can only return curated text or
    the generic fallback.
    """

    def __init__(self) -> None:
        self._entries = _load_kb()
        # The system instruction isn't "used" by the mock in a
        # meaningful way, but we keep a reference so the behavior
        # contract (educational-only) is explicit and identical to what
        # a real provider will be given.
        self._system_instruction = SYSTEM_INSTRUCTION

    @property
    def is_mock(self) -> bool:
        return True

    def generate(self, *, user_message: str, history: list[dict]) -> LLMResult:
        text = user_message.lower()
        best = None
        for entry in self._entries:
            if any(kw in text for kw in entry.get("keywords", [])):
                best = entry
                break

        if best is not None:
            answer = (
                f"{best['answer']}\n\n"
                f"(Educational information. Source: {best.get('source', 'curated FAQ')}.)"
            )
            return LLMResult(content=answer, is_mock=True, source=best.get("source"))

        generic = (
            "I can share general, educational skin-care information. I don't "
            "have a specific curated answer for that yet, and I can't "
            "diagnose or recommend treatment. For a persistent or concerning "
            "skin problem, a doctor or dermatologist is the right person to "
            "help. You could also ask me about cleansing, moisturizing, "
            "sunscreen, mild acne, dry skin, or patch testing."
        )
        return LLMResult(content=generic, is_mock=True, source=None)


class OllamaProvider(LLMProvider):
    """Local model via Ollama's /api/chat. Supports tool calling when the
    chosen model does. Any network/format problem becomes ProviderError
    so the chat endpoint returns a clean 503."""

    supports_tools = True

    def __init__(self) -> None:
        from app.core.config import get_settings

        s = get_settings()
        self._url = s.ollama_base_url.rstrip("/") + "/api/chat"
        self._model = s.ollama_model
        self._timeout = s.ollama_timeout_seconds

    @property
    def is_mock(self) -> bool:
        return False

    def chat(self, *, messages: list[dict], tools: list[dict]) -> AgentStep:
        import httpx

        body: dict = {"model": self._model, "messages": messages, "stream": False}
        if tools:
            body["tools"] = tools
        try:
            resp = httpx.post(self._url, json=body, timeout=self._timeout)
            resp.raise_for_status()
            msg = resp.json()["message"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise ProviderError(f"Ollama request failed: {type(exc).__name__}") from exc

        calls: list[ToolCall] = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function") or {}
            args = fn.get("arguments") or {}
            if isinstance(args, str):  # some models return JSON text
                try:
                    args = json.loads(args)
                except ValueError:
                    args = {}
            if fn.get("name"):
                calls.append(ToolCall(name=fn["name"], arguments=args if isinstance(args, dict) else {}))
        return AgentStep(content=(msg.get("content") or "").strip(), tool_calls=calls)

    def generate(self, *, user_message: str, history: list[dict]) -> LLMResult:
        messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}, *history]
        messages.append({"role": "user", "content": user_message})
        step = self.chat(messages=messages, tools=[])
        if not step.content:
            raise ProviderError("Empty response from model.")
        return LLMResult(content=step.content, is_mock=False)


def _to_openai_messages(messages: list[dict]) -> list[dict]:
    """Our internal message shape -> OpenAI-compatible shape (used by
    Groq). Tool calls get synthetic sequential ids; the matching
    tool-result messages — emitted right after, in the same order, by
    agent_service's loop — reuse those same ids in order."""
    wire: list[dict] = []
    pending_ids: list[str] = []
    counter = 0
    for m in messages:
        role = m["role"]
        if role == "assistant" and m.get("tool_calls"):
            out_calls = []
            for tc in m["tool_calls"]:
                call_id = f"call_{counter}"
                counter += 1
                pending_ids.append(call_id)
                fn = tc["function"]
                out_calls.append(
                    {
                        "id": call_id,
                        "type": "function",
                        "function": {"name": fn["name"], "arguments": json.dumps(fn.get("arguments") or {})},
                    }
                )
            wire.append({"role": "assistant", "content": m.get("content") or None, "tool_calls": out_calls})
        elif role == "tool":
            call_id = pending_ids.pop(0) if pending_ids else f"call_unmatched_{counter}"
            wire.append(
                {"role": "tool", "tool_call_id": call_id, "name": m.get("tool_name", ""), "content": m["content"]}
            )
        else:
            wire.append({"role": role, "content": m["content"]})
    return wire


def _to_gemini_contents(messages: list[dict]):
    """Our internal message shape -> Gemini's Content/Part objects.
    Gemini has no 'system' role, so any system message is pulled out and
    returned separately for GenerateContentConfig.system_instruction."""
    from google.genai import types

    system: str | None = None
    contents: list = []
    for m in messages:
        role = m["role"]
        if role == "system":
            system = (system + "\n\n" if system else "") + m["content"]
        elif role == "assistant" and m.get("tool_calls"):
            parts = [types.Part(text=m["content"])] if m.get("content") else []
            for tc in m["tool_calls"]:
                fn = tc["function"]
                parts.append(types.Part(function_call=types.FunctionCall(name=fn["name"], args=fn.get("arguments") or {})))
            contents.append(types.Content(role="model", parts=parts))
        elif role == "tool":
            # Gemini expects a function result as a "user" turn with a
            # functionResponse part. The `response` field must be a dict;
            # our tool content is already a JSON string, so it is wrapped
            # rather than re-parsed (never fails on odd tool output).
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part(function_response=types.FunctionResponse(name=m.get("tool_name", ""), response={"result": m["content"]}))],
                )
            )
        elif role == "assistant":
            contents.append(types.Content(role="model", parts=[types.Part(text=m["content"])]))
        else:  # user
            contents.append(types.Content(role="user", parts=[types.Part(text=m["content"])]))
    return system, contents


def _to_gemini_tools(tools: list[dict]):
    from google.genai import types

    if not tools:
        return None
    declarations = []
    for t in tools:
        fn = t["function"]
        declarations.append(
            types.FunctionDeclaration(
                name=fn["name"],
                description=fn.get("description", ""),
                parameters=fn.get("parameters") or {"type": "object", "properties": {}},
            )
        )
    return [types.Tool(function_declarations=declarations)]


class GeminiProvider(LLMProvider):
    """Google Gemini via the official google-genai SDK (free tier).
    Cloud-hosted: unlike 'ollama', the conversation text leaves this
    machine on every turn and is subject to Google's terms for the tier
    in use. Raises ProviderError at construction if no key is set, so a
    misconfigured cloud provider never silently serves a half response."""

    supports_tools = True

    def __init__(self) -> None:
        from app.core.config import get_settings

        s = get_settings()
        if not s.gemini_api_key:
            raise ProviderError("GEMINI_API_KEY is not set.")
        from google import genai
        from google.genai import types

        self._client = genai.Client(
            api_key=s.gemini_api_key,
            http_options=types.HttpOptions(timeout=int(s.cloud_llm_timeout_seconds * 1000)),
        )
        self._model = s.gemini_model

    @property
    def is_mock(self) -> bool:
        return False

    def chat(self, *, messages: list[dict], tools: list[dict]) -> AgentStep:
        from google.genai import types

        system, contents = _to_gemini_contents(messages)
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.4,
            max_output_tokens=2000,
            tools=_to_gemini_tools(tools),
        )
        try:
            response = self._client.models.generate_content(model=self._model, contents=contents, config=config)
        except Exception as exc:  # google.genai.errors.APIError, network errors, etc.
            raise ProviderError(f"Gemini request failed: {type(exc).__name__}") from exc

        calls: list[ToolCall] = []
        text_parts: list[str] = []
        candidates = getattr(response, "candidates", None) or []
        parts = candidates[0].content.parts if candidates and candidates[0].content else []
        for part in parts or []:
            fc = getattr(part, "function_call", None)
            if fc is not None:
                calls.append(ToolCall(name=fc.name, arguments=dict(fc.args or {})))
            elif getattr(part, "text", None):
                text_parts.append(part.text)
        return AgentStep(content="".join(text_parts).strip(), tool_calls=calls)

    def generate(self, *, user_message: str, history: list[dict]) -> LLMResult:
        messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}, *history, {"role": "user", "content": user_message}]
        step = self.chat(messages=messages, tools=[])
        if not step.content:
            raise ProviderError("Empty response from Gemini.")
        return LLMResult(content=step.content, is_mock=False)


class GroqProvider(LLMProvider):
    """Groq's OpenAI-compatible chat API via the official groq SDK (free
    tier). Cloud-hosted, same data-leaves-the-machine caveat as Gemini.
    Raises ProviderError at construction if no key is set."""

    supports_tools = True

    def __init__(self) -> None:
        from app.core.config import get_settings

        s = get_settings()
        if not s.groq_api_key:
            raise ProviderError("GROQ_API_KEY is not set.")
        from groq import Groq

        self._client = Groq(api_key=s.groq_api_key, timeout=s.cloud_llm_timeout_seconds)
        self._model = s.groq_model
        extra = [m.strip() for m in (s.groq_fallback_models or "").split(",") if m.strip()]
        self._models = [self._model, *[m for m in extra if m != self._model]]

    @property
    def is_mock(self) -> bool:
        return False

    def chat(self, *, messages: list[dict], tools: list[dict]) -> AgentStep:
        wire = _to_openai_messages(messages)
        kwargs: dict = {
            "messages": wire,
            "temperature": 0.4,
            "max_tokens": 2000,
        }
        if tools:
            # Groq rejects an explicit tool_choice=None body on some models
            # (e.g. openai/gpt-oss-120b) with a 400 - only send these keys
            # at all when there are tools to choose from.
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        from groq import RateLimitError

        response = None
        last_exc: Exception | None = None
        for model in self._models:
            try:
                response = self._client.chat.completions.create(model=model, **kwargs)
                break
            except RateLimitError as exc:
                last_exc = exc  # this model is busy; try the next one
            except Exception as exc:  # groq.APIError, httpx errors, etc.
                raise ProviderError(f"Groq request failed: {type(exc).__name__}") from exc
        if response is None:
            raise ProviderError("Groq request failed: every model is rate-limited.") from last_exc

        msg = response.choices[0].message
        calls: list[ToolCall] = []
        for tc in msg.tool_calls or []:
            args = tc.function.arguments or "{}"
            try:
                args = json.loads(args)
            except ValueError:
                args = {}
            calls.append(ToolCall(name=tc.function.name, arguments=args if isinstance(args, dict) else {}))
        # Qwen-style models may prefix their private reasoning in <think> tags.
        content = re.sub(r"<think>.*?</think>", "", msg.content or "", flags=re.S).strip()
        return AgentStep(content=content, tool_calls=calls)

    def generate(self, *, user_message: str, history: list[dict]) -> LLMResult:
        messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}, *history, {"role": "user", "content": user_message}]
        step = self.chat(messages=messages, tools=[])
        if not step.content:
            raise ProviderError("Empty response from Groq.")
        return LLMResult(content=step.content, is_mock=False)


class ChainedProvider(LLMProvider):
    """Tries each given provider in order (e.g. Gemini, then Groq). A
    provider that fails for this turn is skipped in favour of the next;
    if every one fails, falls back to the offline MockProvider — a fixed,
    clearly-labelled answer, never presented as an AI-generated one. This
    mirrors LLM_PROVIDER=mock's existing honesty contract, just reached
    from the far end of a cloud-provider chain instead of by config."""

    supports_tools = True

    def __init__(self, providers: list[LLMProvider]):
        if not providers:
            raise ValueError("ChainedProvider needs at least one provider.")
        self._providers = providers
        self._mock = MockProvider()
        self._last_is_mock = False

    @property
    def is_mock(self) -> bool:
        return self._last_is_mock

    def chat(self, *, messages: list[dict], tools: list[dict]) -> AgentStep:
        for provider in self._providers:
            if not provider.supports_tools:
                continue  # e.g. a literal "mock" chain entry: it can't .chat(), only .generate()
            try:
                step = provider.chat(messages=messages, tools=tools)
            except ProviderError:
                continue
            self._last_is_mock = provider.is_mock
            return step

        # Every configured provider failed this turn: answer anyway, but
        # never silently — the UI's existing "mock" badge makes this visible.
        self._last_is_mock = True
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        result = self._mock.generate(user_message=last_user, history=[])
        note = "\n\n(The AI assistant is temporarily unavailable, so this is a general answer, not an AI-generated one.)"
        return AgentStep(content=result.content + note, tool_calls=[])

    def generate(self, *, user_message: str, history: list[dict]) -> LLMResult:
        step = self.chat(messages=[{"role": "user", "content": user_message}], tools=[])
        return LLMResult(content=step.content, is_mock=self._last_is_mock)


def _build_single_provider(name: str) -> LLMProvider:
    """One name -> one provider instance. Raises ValueError for a name
    this app doesn't implement, and ProviderError for a recognized cloud
    provider that is missing its required API key."""
    if name == "mock":
        return MockProvider()
    if name == "ollama":
        return OllamaProvider()
    if name == "gemini":
        return GeminiProvider()
    if name == "groq":
        return GroqProvider()
    raise ValueError(f"Unknown LLM provider '{name}'. Implemented: 'mock', 'ollama', 'gemini', 'groq'.")


def get_provider(provider_name: str) -> LLMProvider:
    """Factory, reading credentials from the environment. An unrecognized
    name is always a hard error — we never silently fall back to a
    half-configured real provider.

    If LLM_FALLBACK_CHAIN is set (comma-separated provider names, e.g.
    "groq"), the primary provider is wrapped with those as fallbacks, in
    order, finishing with the offline mock. A fallback-chain member with
    no API key is skipped (not an error); a misspelled one still is."""
    name = (provider_name or "mock").strip().lower()
    primary = _build_single_provider(name)

    from app.core.config import get_settings

    chain_setting = (get_settings().llm_fallback_chain or "").strip()
    if not chain_setting:
        return primary

    chain: list[LLMProvider] = [primary]
    for fallback_name in (n.strip().lower() for n in chain_setting.split(",")):
        if not fallback_name:
            continue
        try:
            chain.append(_build_single_provider(fallback_name))
        except ProviderError:
            continue  # not configured for this fallback slot -> skip, don't fail
    return ChainedProvider(chain)
