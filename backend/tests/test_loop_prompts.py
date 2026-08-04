from unittest.mock import MagicMock
from backend.app.loop.hyde import build_hyde_prompt, run_hyde
from backend.app.loop.relevance_check import build_relevance_check_prompt, run_relevance_check
from backend.app.llm_client import ChatResult


def test_build_hyde_prompt_includes_query():
    messages = build_hyde_prompt("temporal lobe hypometabolism in rare encephalitis")
    joined = " ".join(m["content"] for m in messages)
    assert "temporal lobe hypometabolism in rare encephalitis" in joined


def test_run_hyde_calls_client_and_returns_result():
    fake_client = MagicMock()
    fake_client.chat.return_value = ChatResult(
        content="A hypothetical case report describing...", prompt_tokens=50,
        completion_tokens=80, total_tokens=130)
    result = run_hyde(fake_client, "rare condition query")
    assert result.content.startswith("A hypothetical case report")
    fake_client.chat.assert_called_once()


def test_build_relevance_check_prompt_requests_json():
    messages = build_relevance_check_prompt("query text", "abstract text")
    assert any("json" in m["content"].lower() for m in messages)


def test_run_relevance_check_parses_structured_output():
    fake_client = MagicMock()
    fake_client.chat.return_value = ChatResult(
        content='{"relevant": true, "confidence": 0.82}',
        prompt_tokens=90, completion_tokens=10, total_tokens=100)
    parsed = run_relevance_check(fake_client, "query", "abstract")
    assert parsed == {"relevant": True, "confidence": 0.82}
