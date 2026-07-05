"""Tests for LLM provider resolution (sarvam | openai | mock fallback chain).

Pure resolution logic — no network. The live call path is exercised by evals/
(real API spend), never by pytest.
"""

import pytest

from app.modules.chat.llm_client import LLMClient
from app.platform.config import get_settings


@pytest.fixture(autouse=True)
def _clean_llm_env(monkeypatch):
    # Resolution must depend only on the settings we pin per-test.
    monkeypatch.delenv("MOCK_LLM", raising=False)
    s = get_settings()
    monkeypatch.setattr(s, "mock_openai", False)
    monkeypatch.setattr(s, "chat_provider", "sarvam")
    monkeypatch.setattr(s, "openai_api_key", "")
    monkeypatch.setattr(s, "sarvam_api_key", "")


def test_mock_when_forced_by_env(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "1")
    assert LLMClient()._resolve()[0] == "mock"


def test_mock_when_setting_says_so(monkeypatch):
    monkeypatch.setattr(get_settings(), "mock_openai", True)
    monkeypatch.setattr(get_settings(), "sarvam_api_key", "sk_x")
    assert LLMClient()._resolve()[0] == "mock"


def test_sarvam_is_the_default_when_keyed(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "sarvam_api_key", "sk_sarvam")
    monkeypatch.setattr(s, "openai_api_key", "sk_openai")
    provider, key, base_url, model = LLMClient()._resolve()
    assert provider == "sarvam"
    assert key == "sk_sarvam"
    assert base_url == s.sarvam_base_url
    assert model == s.sarvam_model


def test_keyless_default_falls_back_to_openai(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "openai_api_key", "sk_openai")  # sarvam key empty
    provider, key, base_url, model = LLMClient()._resolve()
    assert provider == "openai"
    assert key == "sk_openai"
    assert base_url is None  # OpenAI default endpoint
    assert model == s.chat_model


def test_explicit_provider_override(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "sarvam_api_key", "sk_sarvam")
    monkeypatch.setattr(s, "openai_api_key", "sk_openai")
    assert LLMClient()._resolve("openai")[0] == "openai"
    assert LLMClient()._resolve("sarvam")[0] == "sarvam"
    # Nonsense values mean "use the default", never an error.
    assert LLMClient()._resolve("gemini")[0] == "sarvam"


def test_sarvam_fast_uses_30b_on_the_same_key(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "sarvam_api_key", "sk_sarvam")
    provider, key, base_url, model = LLMClient()._resolve("sarvam-fast")
    assert provider == "sarvam-fast"
    assert (key, base_url) == ("sk_sarvam", s.sarvam_base_url)
    assert model == s.sarvam_fast_model  # sarvam-30b

    # Keyless sarvam-fast falls back through the flagship chain to openai.
    monkeypatch.setattr(s, "sarvam_api_key", "")
    monkeypatch.setattr(s, "openai_api_key", "sk_openai")
    assert LLMClient()._resolve("sarvam-fast")[0] == "openai"


def test_no_keys_at_all_means_mock():
    assert LLMClient()._resolve()[0] == "mock"


async def test_mock_complete_reports_provider():
    import os

    os.environ["MOCK_LLM"] = "1"
    try:
        client = LLMClient()
        reply = await client.complete("system", [{"role": "user", "content": "hi"}])
        assert reply  # canned Malayalam reply
        meta = client.debug_meta()
        assert meta["mocked"] is True and meta["provider"] == "mock"
    finally:
        os.environ.pop("MOCK_LLM", None)
