from unittest.mock import MagicMock
from backend.app.llm_client import ChatResult
from backend.measurement.multiturn_session import run_multiturn_session


def test_run_multiturn_session_accumulates_per_turn():
    fake_client = MagicMock()
    call_count = {"n": 0}

    def fake_chat(messages, response_format=None, direct=False, max_retries=3):
        call_count["n"] += 1
        base = 50 if direct else 30
        return ChatResult(content="ok", prompt_tokens=base, completion_tokens=5, total_tokens=base + 5)

    fake_client.chat.side_effect = fake_chat
    result = run_multiturn_session(fake_client, turns=3)

    assert len(result["proxied_cumulative"]) == 3
    assert len(result["direct_cumulative"]) == 3
    assert result["direct_cumulative"][-1] > result["proxied_cumulative"][-1]
    assert result["proxied_cumulative"] == sorted(result["proxied_cumulative"])  # non-decreasing
