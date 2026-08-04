from unittest.mock import MagicMock
from backend.app.llm_client import ChatResult
from backend.app.summary.generate import generate_sourced_summary

PAPERS = [
    {"pmid": "111", "title": "Scalp angiosarcoma case report", "abstract": "Focal FDG uptake noted."},
    {"pmid": "222", "title": "Second scalp lesion report", "abstract": "Rare vascular tumor imaging findings."},
]


def test_generate_sourced_summary_returns_text_and_citations():
    fake_client = MagicMock()
    fake_client.chat.return_value = ChatResult(
        content='{"summary": "The lesion shows focal FDG uptake [1], consistent with vascular tumor findings [2].", "imaging_findings": null, "teaching_point": null, "differential": []}',
        prompt_tokens=300, completion_tokens=40, total_tokens=340)

    summary = generate_sourced_summary(fake_client, "scalp lesion PET findings", PAPERS)

    assert "[1]" in summary.text
    assert len(summary.citations) == 2
    assert summary.citations[0] == {"marker": "[1]", "pmid": "111", "title": "Scalp angiosarcoma case report"}
    assert summary.degraded is False


def test_generate_sourced_summary_marks_degraded_on_failure():
    fake_client = MagicMock()
    fake_client.chat.return_value = ChatResult(
        content="", prompt_tokens=0, completion_tokens=0, total_tokens=0, degraded=True, error="timeout")

    summary = generate_sourced_summary(fake_client, "query", PAPERS)

    assert summary.degraded is True
    assert summary.text == ""


def test_generate_sourced_summary_handles_empty_paper_list():
    fake_client = MagicMock()

    summary = generate_sourced_summary(fake_client, "query", [])

    assert summary.text == ""
    assert summary.citations == []
    assert summary.degraded is False
    fake_client.chat.assert_not_called()


def test_generate_sourced_summary_citation_markers_beyond_nine():
    fake_client = MagicMock()
    fake_client.chat.return_value = ChatResult(
        content='{"summary": "Findings summarized across all sources.", "imaging_findings": null, "teaching_point": null, "differential": []}',
        prompt_tokens=500, completion_tokens=40, total_tokens=540)
    many_papers = [{"pmid": str(i), "title": f"Paper {i}", "abstract": "abstract"} for i in range(12)]

    summary = generate_sourced_summary(fake_client, "query", many_papers)

    assert summary.citations[9] == {"marker": "[10]", "pmid": "9", "title": "Paper 9"}
    assert summary.citations[11] == {"marker": "[12]", "pmid": "11", "title": "Paper 11"}


def test_generate_sourced_summary_prepends_disclaimer_when_low_confidence():
    fake_client = MagicMock()
    fake_client.chat.return_value = ChatResult(
        content='{"summary": "The lesion shows focal FDG uptake [1].", "imaging_findings": null, "teaching_point": null, "differential": []}',
        prompt_tokens=300, completion_tokens=40, total_tokens=340)

    summary = generate_sourced_summary(fake_client, "query", PAPERS, low_confidence=True)

    assert summary.text.startswith("Note:")
    assert "The lesion shows focal FDG uptake [1]." in summary.text


def test_generate_sourced_summary_no_disclaimer_by_default():
    fake_client = MagicMock()
    fake_client.chat.return_value = ChatResult(
        content='{"summary": "The lesion shows focal FDG uptake [1].", "imaging_findings": null, "teaching_point": null, "differential": []}',
        prompt_tokens=300, completion_tokens=40, total_tokens=340)

    summary = generate_sourced_summary(fake_client, "query", PAPERS)

    assert summary.text == "The lesion shows focal FDG uptake [1]."


def test_generate_sourced_summary_returns_degraded_on_malformed_json():
    """A ChatResult with invalid JSON should mark degraded=True."""
    fake_client = MagicMock()
    fake_client.chat.return_value = ChatResult(
        content="not valid json",
        prompt_tokens=300, completion_tokens=40, total_tokens=340)

    summary = generate_sourced_summary(fake_client, "query", PAPERS)

    assert summary.degraded is True
    assert summary.text == ""


def test_generate_sourced_summary_returns_degraded_on_missing_summary_key():
    """A ChatResult with valid JSON but missing 'summary' key should mark degraded=True."""
    fake_client = MagicMock()
    fake_client.chat.return_value = ChatResult(
        content='{"foo": "bar"}',
        prompt_tokens=300, completion_tokens=40, total_tokens=340)

    summary = generate_sourced_summary(fake_client, "query", PAPERS)

    assert summary.degraded is True
    assert summary.text == ""


def test_generate_sourced_summary_populates_imaging_findings_teaching_point_and_differential():
    """Test that imaging_findings, teaching_point, and differential_candidates are populated from JSON."""
    fake_client = MagicMock()
    fake_client.chat.return_value = ChatResult(
        content='{"summary": "Findings [1].", "imaging_findings": "Occipital hypometabolism.", "teaching_point": "Consider CJD.", "differential": [{"condition_name": "Alzheimer disease", "marker": "[1]"}]}',
        prompt_tokens=300, completion_tokens=40, total_tokens=340)

    summary = generate_sourced_summary(fake_client, "query", PAPERS)

    assert summary.imaging_findings == "Occipital hypometabolism."
    assert summary.teaching_point == "Consider CJD."
    assert summary.differential_candidates == [{"condition_name": "Alzheimer disease", "marker": "[1]"}]
    assert summary.degraded is False


def test_generate_sourced_summary_drops_malformed_differential_items():
    """Test that malformed differential items are dropped while valid siblings survive."""
    fake_client = MagicMock()
    fake_client.chat.return_value = ChatResult(
        content='{"summary": "Findings [1].", "imaging_findings": null, "teaching_point": null, "differential": [{"condition_name": "Bad"}, {"condition_name": "Good", "marker": "[1]"}]}',
        prompt_tokens=300, completion_tokens=40, total_tokens=340)

    summary = generate_sourced_summary(fake_client, "query", PAPERS)

    assert summary.differential_candidates == [{"condition_name": "Good", "marker": "[1]"}]
    assert summary.degraded is False
