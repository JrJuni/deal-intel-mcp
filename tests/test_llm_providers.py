from __future__ import annotations

import pytest

from deal_intel.providers.llm import (
    AnthropicProvider,
    OpenAIAPIProvider,
    _extract_openai_output_text,
    make_llm_provider,
)


class FakeHTTPResponse:
    def __init__(self, status_code: int, payload: dict, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self) -> dict:
        return self._payload


def test_openai_api_provider_ping_reports_missing_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    provider = OpenAIAPIProvider()

    assert provider.ping() == {
        "status": "missing_key",
        "message": "OPENAI_API_KEY not set",
        "fix": "Set OPENAI_API_KEY in .env or ~/.deal-intel/config.yaml.",
    }


def test_openai_api_provider_defaults_to_cost_control_model(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    provider = OpenAIAPIProvider()

    assert provider.ping() == {"status": "ok", "model": "gpt-5.4-mini"}


def test_openai_api_provider_posts_responses_payload(monkeypatch) -> None:
    seen: dict = {}

    def fake_post(url, *, headers, json, timeout):
        seen["url"] = url
        seen["headers"] = headers
        seen["json"] = json
        seen["timeout"] = timeout
        return FakeHTTPResponse(
            200,
            {
                "status": "completed",
                "model": "gpt-5.5",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {"type": "output_text", "text": "hello from api"}
                        ],
                    }
                ],
                "usage": {
                    "input_tokens": 11,
                    "output_tokens": 7,
                    "total_tokens": 18,
                    "input_tokens_details": {"cached_tokens": 3},
                    "output_tokens_details": {"reasoning_tokens": 2},
                },
            },
        )

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)
    provider = OpenAIAPIProvider(
        model="gpt-5.5",
        api_key="test-key",
        reasoning_effort="low",
    )

    result = provider.chat_once(
        system="System prompt",
        user="User prompt",
        max_tokens=123,
        temperature=0.2,
    )

    assert result.text == "hello from api"
    assert result.model == "gpt-5.5"
    assert result.usage == {
        "input_tokens": 11,
        "output_tokens": 7,
        "total_tokens": 18,
        "cached_input_tokens": 3,
        "reasoning_output_tokens": 2,
    }
    assert seen["url"] == "https://api.openai.com/v1/responses"
    assert seen["headers"]["Authorization"] == "Bearer test-key"
    assert seen["json"] == {
        "model": "gpt-5.5",
        "instructions": "System prompt",
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": "User prompt"}],
            }
        ],
        "max_output_tokens": 123,
        "store": False,
        "temperature": 0.2,
        "reasoning": {"effort": "low"},
    }
    assert seen["timeout"] == 120


def test_openai_api_provider_chat_cached_concatenates_context(monkeypatch) -> None:
    seen: dict = {}

    def fake_post(_url, *, headers, json, timeout):
        seen["json"] = json
        return FakeHTTPResponse(
            200,
            {
                "status": "completed",
                "model": "gpt-5.5",
                "output_text": "cached reply",
                "usage": {},
            },
        )

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)
    provider = OpenAIAPIProvider(api_key="test-key", reasoning_effort=None)

    result = provider.chat_cached(
        system="system",
        cached_context="cached",
        volatile_context="volatile",
        task="task",
    )

    assert result.text == "cached reply"
    assert seen["json"]["model"] == "gpt-5.4-mini"
    assert seen["json"]["input"][0]["content"][0]["text"] == (
        "cached\n\nvolatile\n\ntask"
    )
    assert "reasoning" not in seen["json"]


def test_openai_api_provider_raises_clear_http_error(monkeypatch) -> None:
    def fake_post(_url, *, headers, json, timeout):
        return FakeHTTPResponse(
            429,
            {"error": {"message": "insufficient quota"}},
        )

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)
    provider = OpenAIAPIProvider(api_key="test-key")

    with pytest.raises(RuntimeError, match="OpenAI API returned 429: insufficient quota"):
        provider.chat_once(system="s", user="u")


def test_openai_api_provider_rejects_invalid_reasoning_effort() -> None:
    with pytest.raises(ValueError, match="openai_api_reasoning_effort"):
        OpenAIAPIProvider(api_key="test-key", reasoning_effort="turbo")


def test_make_llm_provider_supports_openai_api(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    provider = make_llm_provider({
        "llm": {
            "provider": "openai_api",
            "openai_api_model": "gpt-5.4-mini",
            "openai_api_reasoning_effort": "none",
        }
    })

    assert isinstance(provider, OpenAIAPIProvider)
    assert provider.ping() == {"status": "ok", "model": "gpt-5.4-mini"}


def test_make_llm_provider_preserves_anthropic_default() -> None:
    provider = make_llm_provider({"llm": {"provider": "anthropic"}})

    assert isinstance(provider, AnthropicProvider)


def test_extract_openai_output_text_supports_sdk_convenience_field() -> None:
    assert _extract_openai_output_text({"output_text": "hello"}) == "hello"
