import json
from dataclasses import dataclass

from backend.contracts.models import ChatResult, ResearcherProfile, TokenUsage
from backend.memory.profile import (
    MAX_DISTILLED_CONTEXT_CHARS,
    distill_profile,
    should_distill,
)


@dataclass
class _StubLLM:
    content: str = ""
    degraded: bool = False

    def chat(self, messages, **kwargs):
        usage = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15, model="stub", cost_usd=0.0)
        return ChatResult(content=self.content, usage=usage, degraded=self.degraded)

    def health(self):
        return {"ok": True, "detail": "stub"}


def _profile(query_count: int) -> ResearcherProfile:
    return ResearcherProfile(user_id="u1", specialty="neuroradiology", query_count=query_count)


def test_should_distill_on_multiple_of_three():
    assert should_distill(3, specialty_changed=False) is True
    assert should_distill(6, specialty_changed=False) is True
    assert should_distill(2, specialty_changed=False) is False
    assert should_distill(0, specialty_changed=False) is False


def test_should_distill_on_specialty_change_regardless_of_count():
    assert should_distill(1, specialty_changed=True) is True


def test_distill_profile_hard_truncates_at_600_chars():
    llm = _StubLLM(content=json.dumps({"distilled_context": "x" * 1000}))

    result = distill_profile(llm, _profile(3), request_id="r1", session_id="s1", user_id="u1")

    assert len(result) == MAX_DISTILLED_CONTEXT_CHARS


def test_distill_profile_strips_pmid_references():
    llm = _StubLLM(content=json.dumps({
        "distilled_context": "Has reviewed PMID 12345678 and PMID: 87654321 in depth."
    }))

    result = distill_profile(llm, _profile(3), request_id="r1", session_id="s1", user_id="u1")

    assert "12345678" not in result
    assert "87654321" not in result


def test_distill_profile_falls_back_to_existing_context_when_degraded():
    llm = _StubLLM(degraded=True)
    profile = ResearcherProfile(user_id="u1", specialty=None, query_count=3, distilled_context="prior context")

    result = distill_profile(llm, profile, request_id="r1", session_id="s1", user_id="u1")

    assert result == "prior context"


def test_distill_profile_falls_back_to_existing_context_on_bad_json():
    llm = _StubLLM(content="not json")
    profile = ResearcherProfile(user_id="u1", specialty=None, query_count=3, distilled_context="prior context")

    result = distill_profile(llm, profile, request_id="r1", session_id="s1", user_id="u1")

    assert result == "prior context"
