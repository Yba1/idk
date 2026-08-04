import pytest
from unittest.mock import MagicMock, patch
from backend.app.llm_client import compress_for_prompt


class MockCompressionResult:
    """Mock result from CompressionPipeline.compress()."""
    def __init__(self, compressed: str, original_tokens: int, compressed_tokens: int):
        self.compressed = compressed
        self.original_tokens = original_tokens
        self.compressed_tokens = compressed_tokens


def test_compress_for_prompt_returns_correct_structure():
    """Test that compress_for_prompt returns (text, original_tokens, compressed_tokens)."""
    mock_result = MockCompressionResult(
        compressed="compressed text here",
        original_tokens=1000,
        compressed_tokens=500
    )

    with patch("backend.app.llm_client._get_compression_pipeline") as mock_get_pipeline:
        mock_pipeline = MagicMock()
        mock_pipeline.compress.return_value = mock_result
        mock_get_pipeline.return_value = mock_pipeline

        text, orig_tokens, comp_tokens = compress_for_prompt(
            "long content here",
            "query text"
        )

        assert text == "compressed text here"
        assert orig_tokens == 1000
        assert comp_tokens == 500


def test_compress_for_prompt_passes_query_and_model():
    """Test that compress_for_prompt passes query and upstream_model to pipeline.compress()."""
    mock_result = MockCompressionResult("result", 100, 50)

    with patch("backend.app.llm_client._get_compression_pipeline") as mock_get_pipeline:
        with patch("backend.app.llm_client.MODEL", "test-model"):
            mock_pipeline = MagicMock()
            mock_pipeline.compress.return_value = mock_result
            mock_get_pipeline.return_value = mock_pipeline

            compress_for_prompt("content", "my query")

            # Verify compress was called with correct arguments
            mock_pipeline.compress.assert_called_once()
            call_args = mock_pipeline.compress.call_args
            assert call_args[0][0] == "content"  # first positional arg
            assert call_args[1]["query"] == "my query"
            assert call_args[1]["upstream_model"] == "test-model"


def test_compress_for_prompt_no_compression_case():
    """Test that no-compression case (original == compressed) returns without error."""
    content = "small content"
    mock_result = MockCompressionResult(
        compressed="small content",  # no change
        original_tokens=50,
        compressed_tokens=50  # same as original
    )

    with patch("backend.app.llm_client._get_compression_pipeline") as mock_get_pipeline:
        mock_pipeline = MagicMock()
        mock_pipeline.compress.return_value = mock_result
        mock_get_pipeline.return_value = mock_pipeline

        text, orig_tokens, comp_tokens = compress_for_prompt(content, "query")

        assert text == "small content"
        assert orig_tokens == 50
        assert comp_tokens == 50


def test_compress_for_prompt_zero_tokens_edge_case():
    """Test edge case where token counts are zero."""
    mock_result = MockCompressionResult(
        compressed="",
        original_tokens=0,
        compressed_tokens=0
    )

    with patch("backend.app.llm_client._get_compression_pipeline") as mock_get_pipeline:
        mock_pipeline = MagicMock()
        mock_pipeline.compress.return_value = mock_result
        mock_get_pipeline.return_value = mock_pipeline

        text, orig_tokens, comp_tokens = compress_for_prompt("", "")

        assert text == ""
        assert orig_tokens == 0
        assert comp_tokens == 0


def test_compress_for_prompt_high_compression_ratio():
    """Test case where compression achieves significant token reduction."""
    mock_result = MockCompressionResult(
        compressed="compressed",
        original_tokens=5000,
        compressed_tokens=1000
    )

    with patch("backend.app.llm_client._get_compression_pipeline") as mock_get_pipeline:
        mock_pipeline = MagicMock()
        mock_pipeline.compress.return_value = mock_result
        mock_get_pipeline.return_value = mock_pipeline

        text, orig_tokens, comp_tokens = compress_for_prompt(
            "very long content " * 1000,
            "query"
        )

        assert orig_tokens > comp_tokens
        assert comp_tokens / orig_tokens == 0.2  # 80% reduction
