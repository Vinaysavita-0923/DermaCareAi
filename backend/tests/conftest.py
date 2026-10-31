"""
Test-wide guardrail: settings are loaded from the real .env at import time
(see app/core/config.py), so without this, a developer's local LLM_PROVIDER
(e.g. gemini/groq, with real keys) would leak into every test run - slow,
flaky, burns API quota, and breaks tests that assert the mock provider's
`is_mock` contract. Force "mock" with no cloud keys for every test; tests
that specifically exercise Gemini/Groq/the agent already monkeypatch their
own settings or provider on top of this.
"""
from __future__ import annotations

import pytest

from app.core.config import get_settings


@pytest.fixture(autouse=True)
def _mock_llm_by_default(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "llm_provider", "mock")
    monkeypatch.setattr(settings, "llm_fallback_chain", None)
    monkeypatch.setattr(settings, "gemini_api_key", None)
    monkeypatch.setattr(settings, "groq_api_key", None)
