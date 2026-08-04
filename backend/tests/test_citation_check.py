"""Tests for citation verification module."""
from unittest.mock import MagicMock, patch
import pytest

from backend.app.llm_client import ChatResult
from backend.app.verify.citation_check import check_citations, split_cited_sentences
from backend.app.summary.generate import LOW_CONFIDENCE_DISCLAIMER, SPARSE_COVERAGE_NOTE


class TestSplitCitedSentences:
    """Tests for sentence splitting and marker detection."""

    def test_split_single_sentence_with_marker(self):
        text = "This is a claim [1]."
        result = split_cited_sentences(text)
        assert len(result) == 1
        assert result[0]["sentence"] == "This is a claim [1]."
        assert result[0]["markers"] == ["[1]"]

    def test_split_multiple_sentences_with_different_markers(self):
        text = "First claim [1]. Second claim [2]."
        result = split_cited_sentences(text)
        assert len(result) == 2
        assert result[0]["sentence"] == "First claim [1]."
        assert result[0]["markers"] == ["[1]"]
        assert result[1]["sentence"] == "Second claim [2]."
        assert result[1]["markers"] == ["[2]"]

    def test_split_sentence_with_multiple_markers(self):
        text = "Both papers [1] and [2] agree."
        result = split_cited_sentences(text)
        assert len(result) == 1
        assert "[1]" in result[0]["markers"]
        assert "[2]" in result[0]["markers"]

    def test_split_sentence_without_markers(self):
        text = "This claim has no citation."
        result = split_cited_sentences(text)
        assert len(result) == 1
        assert result[0]["sentence"] == "This claim has no citation."
        assert result[0]["markers"] == []

    def test_split_empty_text(self):
        result = split_cited_sentences("")
        assert result == []

    def test_split_with_multiple_spaces_between_sentences(self):
        text = "First claim [1].  Second claim [2]."
        result = split_cited_sentences(text)
        assert len(result) == 2


class TestCheckCitationsWithJudge:
    """Tests for the full citation check workflow."""

    def test_empty_papers_and_text_returns_empty_list(self):
        fake_client = MagicMock()
        result = check_citations(fake_client, "test query", "", [])
        assert result == []

    def test_uncited_sentence_flagged_without_llm_call(self):
        """A sentence with no [N] marker should be flagged as uncited without
        consuming a judge call."""
        fake_client = MagicMock()
        raw_text = "This claim has no citation."
        papers = [{"pmid": "1", "abstract": "abstract"}]

        results = check_citations(fake_client, "query", raw_text, papers)

        # Should be flagged as uncited
        assert len(results) == 1
        assert results[0]["status"] == "uncited"
        assert results[0]["marker"] is None
        # Judge should not have been called
        assert not fake_client.chat.called

    def test_invalid_marker_flagged_without_llm_call(self):
        """A marker like [5] when only 2 papers exist should be flagged as
        invalid_marker without consuming a judge call."""
        fake_client = MagicMock()
        raw_text = "This cites a non-existent paper [5]."
        papers = [
            {"pmid": "1", "abstract": "abstract 1"},
            {"pmid": "2", "abstract": "abstract 2"},
        ]

        results = check_citations(fake_client, "query", raw_text, papers)

        # Should be flagged as invalid_marker
        assert len(results) == 1
        assert results[0]["status"] == "invalid_marker"
        assert results[0]["marker"] == "[5]"
        # Judge should not have been called
        assert not fake_client.chat.called

    def test_supported_claim_from_judge(self):
        """A valid marker should trigger a judge call, and judge's 'supported'
        status should be returned."""
        fake_client = MagicMock()
        judge_response = '{"results": [{"marker": "[1]", "sentence_index": 0, "status": "supported", "reason": "Abstract clearly mentions the finding."}]}'
        fake_client.chat.return_value = ChatResult(
            content=judge_response,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )

        raw_text = "The patient showed focal uptake [1]."
        papers = [{"pmid": "1", "abstract": "Focal FDG uptake observed in scans."}]

        results = check_citations(fake_client, "query", raw_text, papers)

        assert len(results) == 1
        assert results[0]["status"] == "supported"
        assert results[0]["marker"] == "[1]"
        assert "[1]" in str(fake_client.chat.call_args)

    def test_unsupported_claim_from_judge(self):
        """Judge marking a claim as 'unsupported' should be returned."""
        fake_client = MagicMock()
        judge_response = '{"results": [{"marker": "[1]", "sentence_index": 0, "status": "unsupported", "reason": "Abstract does not mention this finding."}]}'
        fake_client.chat.return_value = ChatResult(
            content=judge_response,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )

        raw_text = "The patient had seizures [1]."
        papers = [{"pmid": "1", "abstract": "No seizures mentioned in this case."}]

        results = check_citations(fake_client, "query", raw_text, papers)

        assert len(results) == 1
        assert results[0]["status"] == "unsupported"
        assert results[0]["reason"] == "Abstract does not mention this finding."

    def test_degraded_judge_call_marks_all_as_unverified(self):
        """When the judge call degrades, all validated (sentence, marker) pairs
        should be marked as 'unverified', not 'unsupported'."""
        fake_client = MagicMock()
        fake_client.chat.return_value = ChatResult(
            content="",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            degraded=True,
        )

        raw_text = "First claim [1]. Second claim [2]."
        papers = [
            {"pmid": "1", "abstract": "abstract 1"},
            {"pmid": "2", "abstract": "abstract 2"},
        ]

        results = check_citations(fake_client, "query", raw_text, papers)

        # Both claims should be unverified (not unsupported)
        assert len(results) == 2
        assert all(r["status"] == "unverified" for r in results)
        assert "proxy unavailable" in results[0]["reason"].lower()

    def test_json_parsing_failure_marks_all_as_unverified(self):
        """When judge returns invalid JSON, all pairs in that batch should be
        marked as 'unverified'."""
        fake_client = MagicMock()
        fake_client.chat.return_value = ChatResult(
            content="{ not valid json }",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )

        raw_text = "Claim [1]."
        papers = [{"pmid": "1", "abstract": "abstract"}]

        results = check_citations(fake_client, "query", raw_text, papers)

        assert len(results) == 1
        assert results[0]["status"] == "unverified"
        assert "invalid JSON" in results[0]["reason"]

    def test_judge_called_with_direct_true(self):
        """Verify that the judge call passes direct=True (not routed through proxy)."""
        fake_client = MagicMock()
        fake_client.chat.return_value = ChatResult(
            content='{"results": [{"marker": "[1]", "sentence_index": 0, "status": "supported", "reason": "Test"}]}',
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )

        raw_text = "Claim [1]."
        papers = [{"pmid": "1", "abstract": "abstract"}]

        check_citations(fake_client, "query", raw_text, papers)

        # Verify direct=True was passed
        call_kwargs = fake_client.chat.call_args[1]
        assert call_kwargs.get("direct") is True

    def test_judge_not_called_for_uncited_and_invalid_markers(self):
        """Build a raw_text with both uncited and invalid markers - judge should
        only be called if there are valid markers to check."""
        fake_client = MagicMock()
        fake_client.chat.return_value = ChatResult(
            content='{"results": []}',
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
        )

        raw_text = "No citation here. Bad marker [99]."
        papers = [{"pmid": "1", "abstract": "abstract"}]

        results = check_citations(fake_client, "query", raw_text, papers)

        # Both should be flagged (uncited and invalid_marker)
        assert len(results) == 2
        assert results[0]["status"] == "uncited"
        assert results[1]["status"] == "invalid_marker"
        # Judge should not have been called because there are no valid markers
        assert not fake_client.chat.called

    def test_mixed_cited_uncited_and_invalid_markers(self):
        """A mix of uncited sentences, invalid markers, and valid citations."""
        fake_client = MagicMock()
        judge_response = '{"results": [{"marker": "[1]", "sentence_index": 0, "status": "supported", "reason": "Test"}]}'
        fake_client.chat.return_value = ChatResult(
            content=judge_response,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )

        raw_text = "No citation. Valid claim [1]. Bad marker [5]."
        papers = [{"pmid": "1", "abstract": "abstract"}]

        results = check_citations(fake_client, "query", raw_text, papers)

        # Should have 3 results: uncited, supported, invalid_marker
        assert len(results) == 3
        statuses = {r["status"] for r in results}
        assert "uncited" in statuses
        assert "supported" in statuses
        assert "invalid_marker" in statuses

    def test_disclaimer_not_checked_when_passed_raw_text_without_disclaimer(self):
        """The raw_text parameter should NOT contain disclaimers. This test
        demonstrates that calling check_citations with the raw (undisclaimed)
        content never sees a disclaimer sentence to flag as uncited."""
        fake_client = MagicMock()
        fake_client.chat.return_value = ChatResult(
            content='{"results": [{"marker": "[1]", "sentence_index": 0, "status": "supported", "reason": "Test"}]}',
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )

        # Simulate generate_sourced_summary's behavior:
        # raw_text contains ONLY the LLM's actual output (no disclaimer)
        raw_text = "Finding shows focal uptake [1]."
        # summary.text (shown to user) would include the disclaimer:
        summary_text_with_disclaimer = LOW_CONFIDENCE_DISCLAIMER + raw_text

        papers = [{"pmid": "1", "abstract": "Focal uptake described."}]

        # Call check_citations on raw_text (as query.py should)
        results = check_citations(fake_client, "query", raw_text, papers)

        # No disclaimer sentence should appear in the results
        disclaimer_in_results = any(
            LOW_CONFIDENCE_DISCLAIMER in r.get("sentence", "")
            for r in results
        )
        assert not disclaimer_in_results, \
            "Disclaimer should not appear in results when passed raw_text"

    def test_response_format_json_object_used(self):
        """Verify that response_format={'type': 'json_object'} is passed to chat."""
        fake_client = MagicMock()
        fake_client.chat.return_value = ChatResult(
            content='{"results": []}',
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
        )

        raw_text = "Claim [1]."
        papers = [{"pmid": "1", "abstract": "abstract"}]

        check_citations(fake_client, "query", raw_text, papers)

        # Check that response_format was set correctly
        call_kwargs = fake_client.chat.call_args[1]
        assert call_kwargs.get("response_format") == {"type": "json_object"}

    def test_compress_for_prompt_not_used(self):
        """Ensure that compress_for_prompt is NOT used in check_citations module."""
        import backend.app.verify.citation_check as cc_module
        # Verify the module doesn't import compress_for_prompt
        assert not hasattr(cc_module, 'compress_for_prompt'), \
            "citation_check should not import compress_for_prompt"


class TestCheckDifferential:
    """Tests for the differential diagnosis verification function."""

    def test_empty_candidates_list_returns_empty_without_judge_call(self):
        """Empty candidates list should return [] without calling client.chat."""
        from backend.app.verify.citation_check import check_differential
        fake_client = MagicMock()
        papers = [{"pmid": "1", "abstract": "abstract"}]

        result = check_differential(fake_client, papers, [])

        assert result == []
        assert not fake_client.chat.called

    def test_valid_marker_with_supported_status_returns_in_output(self):
        """A candidate with valid marker and 'supported' status should be returned."""
        from backend.app.verify.citation_check import check_differential
        fake_client = MagicMock()
        judge_response = '{"results": [{"condition_name": "Alzheimer disease", "marker": "[1]", "status": "supported", "reason": "Abstract mentions cognitive decline."}]}'
        fake_client.chat.return_value = ChatResult(
            content=judge_response,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )

        papers = [{"pmid": "1", "abstract": "Cognitive decline observed in patient."}]
        candidates = [{"condition_name": "Alzheimer disease", "marker": "[1]"}]

        result = check_differential(fake_client, papers, candidates)

        assert len(result) == 1
        assert result[0]["condition_name"] == "Alzheimer disease"
        assert result[0]["marker"] == "[1]"
        assert result[0]["pmid"] == "1"

    def test_unsupported_status_is_dropped(self):
        """A candidate with 'unsupported' status should not appear in output."""
        from backend.app.verify.citation_check import check_differential
        fake_client = MagicMock()
        judge_response = '{"results": [{"condition_name": "Parkinson disease", "marker": "[1]", "status": "unsupported", "reason": "No mention of motor symptoms."}]}'
        fake_client.chat.return_value = ChatResult(
            content=judge_response,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )

        papers = [{"pmid": "1", "abstract": "Cognitive findings only."}]
        candidates = [{"condition_name": "Parkinson disease", "marker": "[1]"}]

        result = check_differential(fake_client, papers, candidates)

        assert result == []

    def test_out_of_range_marker_is_dropped_without_judge_call(self):
        """A candidate with out-of-range marker should be dropped, and if it's the only one,
        judge should not be called."""
        from backend.app.verify.citation_check import check_differential
        fake_client = MagicMock()
        papers = [{"pmid": "1", "abstract": "abstract"}]
        candidates = [{"condition_name": "Some disease", "marker": "[99]"}]

        result = check_differential(fake_client, papers, candidates)

        assert result == []
        assert not fake_client.chat.called

    def test_same_marker_different_conditions_independent_verdicts(self):
        """Two candidates with the same marker but different condition_names should
        have independent verdicts keyed by (condition_name, marker) tuple."""
        from backend.app.verify.citation_check import check_differential
        fake_client = MagicMock()
        judge_response = '{"results": [{"condition_name": "Alzheimer disease", "marker": "[1]", "status": "supported", "reason": "Supported."}, {"condition_name": "Parkinson disease", "marker": "[1]", "status": "unsupported", "reason": "Not supported."}]}'
        fake_client.chat.return_value = ChatResult(
            content=judge_response,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )

        papers = [{"pmid": "1", "abstract": "abstract"}]
        candidates = [
            {"condition_name": "Alzheimer disease", "marker": "[1]"},
            {"condition_name": "Parkinson disease", "marker": "[1]"},
        ]

        result = check_differential(fake_client, papers, candidates)

        assert len(result) == 1
        assert result[0]["condition_name"] == "Alzheimer disease"

    def test_degraded_judge_call_returns_empty_list(self):
        """When the judge call degrades, check_differential should return []."""
        from backend.app.verify.citation_check import check_differential
        fake_client = MagicMock()
        fake_client.chat.return_value = ChatResult(
            content="",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            degraded=True,
        )

        papers = [{"pmid": "1", "abstract": "abstract"}]
        candidates = [{"condition_name": "Alzheimer disease", "marker": "[1]"}]

        result = check_differential(fake_client, papers, candidates)

        assert result == []
