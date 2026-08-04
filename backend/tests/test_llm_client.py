import httpx
import pytest
from openai import APITimeoutError
from backend.app.llm_client import ChatResult, ParitokLLMClient


def test_chat_result_defaults():
    result = ChatResult(content="ok", prompt_tokens=10, completion_tokens=2, total_tokens=12)
    assert result.degraded is False
    assert result.error is None


def test_client_reads_env_base_url_and_key(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:8080")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    client = ParitokLLMClient()
    assert client.proxy_base_url == "http://127.0.0.1:8080"
    assert client.api_key == "test-key"


def test_client_raises_without_env(monkeypatch):
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        ParitokLLMClient()


def _timeout_error() -> APITimeoutError:
    return APITimeoutError(request=httpx.Request("POST", "http://example.invalid"))


class _FakeCompletions:
    def __init__(self, side_effect):
        self._side_effect = side_effect

    def create(self, **kwargs):
        if isinstance(self._side_effect, Exception):
            raise self._side_effect
        return self._side_effect


def _fake_response(content: str):
    return type(
        "FakeResponse",
        (),
        {
            "choices": [type("Choice", (), {"message": type("Msg", (), {"content": content})()})()],
            "usage": type("Usage", (), {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8})(),
        },
    )()


def test_client_has_no_gemini_fallback_without_key(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:8080")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    client = ParitokLLMClient()
    assert client._gemini_client is None


def test_falls_back_to_gemini_when_groq_exhausted(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:8080")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    client = ParitokLLMClient()
    assert client._gemini_client is not None

    client._proxy_client.chat.completions = _FakeCompletions(_timeout_error())
    client._gemini_client.chat.completions = _FakeCompletions(_fake_response("gemini said hi"))

    result = client.chat([{"role": "user", "content": "hi"}], max_retries=1)

    assert result.degraded is False
    assert result.content == "gemini said hi"
