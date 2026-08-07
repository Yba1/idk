import json

from backend.app.summary.generate import SUMMARY_SYSTEM_PROMPT, generate_sourced_summary
from backend.tests._stub_llm import StubLLM, make_scored_paper


def test_no_papers_returns_empty_summary_without_a_call():
    llm = StubLLM({"summary": json.dumps({"summary_markdown": "should not be used"})})
    summary = generate_sourced_summary(llm, "query", [], request_id="r1", session_id="s1", user_id="u1")
    assert summary.markdown == ""
    assert summary.citations == []
    assert summary.degraded is False
    assert llm.calls == []


def test_extracts_citations_from_bracket_markers_in_order():
    papers = [make_scored_paper("p1"), make_scored_paper("p2")]
    llm = StubLLM({"summary": json.dumps({
        "summary_markdown": "First finding [1]. Second finding [2]. Repeat of first [1]."
    })})

    summary = generate_sourced_summary(llm, "query", papers, request_id="r1", session_id="s1", user_id="u1")

    assert summary.degraded is False
    assert [c.index for c in summary.citations] == [1, 2]
    assert [c.pmid for c in summary.citations] == ["p1", "p2"]
    assert all(c.supported is None for c in summary.citations)


def test_out_of_range_markers_are_ignored():
    papers = [make_scored_paper("p1")]
    llm = StubLLM({"summary": json.dumps({"summary_markdown": "Claim [1] and a bad one [9]."})})

    summary = generate_sourced_summary(llm, "query", papers, request_id="r1", session_id="s1", user_id="u1")

    assert [c.index for c in summary.citations] == [1]


def test_degraded_call_returns_degraded_summary():
    papers = [make_scored_paper("p1")]
    llm = StubLLM({}, degraded_sites={"summary"})

    summary = generate_sourced_summary(llm, "query", papers, request_id="r1", session_id="s1", user_id="u1")

    assert summary.degraded is True
    assert summary.markdown == ""
    assert summary.citations == []


def test_missing_summary_markdown_key_is_treated_as_degraded():
    papers = [make_scored_paper("p1")]
    llm = StubLLM({"summary": json.dumps({"not_the_right_key": "oops"})})

    summary = generate_sourced_summary(llm, "query", papers, request_id="r1", session_id="s1", user_id="u1")

    assert summary.degraded is True


def test_distilled_context_is_injected_as_a_system_message():
    papers = [make_scored_paper("p1")]
    llm = StubLLM({"summary": json.dumps({"summary_markdown": "Findings [1]."})})

    generate_sourced_summary(
        llm, "query", papers, distilled_context="neuroradiology resident, explored 3 conditions",
        request_id="r1", session_id="s1", user_id="u1",
    )

    call_site, messages = llm.calls[0]
    assert call_site == "summary"
    assert any("neuroradiology resident" in m.content for m in messages)
    assert any("Do not mention this description" in m.content for m in messages)


def test_no_distilled_context_means_no_extra_system_message():
    papers = [make_scored_paper("p1")]
    llm = StubLLM({"summary": json.dumps({"summary_markdown": "Findings [1]."})})

    generate_sourced_summary(llm, "query", papers, request_id="r1", session_id="s1", user_id="u1")

    _, messages = llm.calls[0]
    assert not any("reader is described as" in m.content for m in messages)


def test_personalization_never_weakens_the_citation_requirement():
    """Every sentence still carries a numbered citation, personalized or not
    - the distilled_context message is additive, never a replacement for the
    citation-instruction system prompt."""
    papers = [make_scored_paper("p1")]
    llm = StubLLM({"summary": json.dumps({"summary_markdown": "Findings [1]."})})

    generate_sourced_summary(
        llm, "query", papers, distilled_context="neuroradiology resident",
        request_id="r1", session_id="s1", user_id="u1",
    )

    _, personalized_messages = llm.calls[0]
    assert any(m.content == SUMMARY_SYSTEM_PROMPT for m in personalized_messages)

    llm2 = StubLLM({"summary": json.dumps({"summary_markdown": "Findings [1]."})})
    generate_sourced_summary(llm2, "query", papers, request_id="r2", session_id="s1", user_id="u1")
    _, plain_messages = llm2.calls[0]

    # Same constant, byte-for-byte, in both calls - personalization adds a
    # message, it never edits this one.
    assert any(m.content == SUMMARY_SYSTEM_PROMPT for m in plain_messages)
