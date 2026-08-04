from unittest.mock import MagicMock
from backend.app.llm_client import ChatResult
from backend.measurement.candidate_a_loop import run_candidate_a


def test_run_candidate_a_sums_tokens_across_calls_and_computes_reduction():
    fake_client = MagicMock()

    def fake_chat(messages, response_format=None, direct=False, max_retries=3):
        base = 100 if direct else 70  # direct (uncompressed) always costs more in this fake
        return ChatResult(content='{"relevant": false, "confidence": 0.3}',
                           prompt_tokens=base, completion_tokens=10, total_tokens=base + 10)

    fake_client.chat.side_effect = fake_chat
    result = run_candidate_a(fake_client)

    assert result["direct_prompt_tokens"] > result["proxied_prompt_tokens"]
    assert result["reduction_pct"] == pytest_approx(30.0)


def pytest_approx(value, tol=0.5):
    class Approx:
        def __eq__(self, other):
            return abs(other - value) <= tol
    return Approx()
