"""Tier 1 -- credential-free. Extractive compression (backend/app/llm/compress.py)."""
from __future__ import annotations

from backend.app.llm.compress import (
    CompressionResult,
    aggregate_reduction_pct,
    compress_abstract,
    compress_papers_for_prompt,
)

_LONG_ABSTRACT = (
    "Scalp angiosarcoma is a rare and aggressive vascular malignancy. "
    "It most commonly presents in elderly patients as an ill-defined bruise-like lesion. "
    "FDG-PET imaging shows markedly increased uptake in the affected scalp region. "
    "Treatment typically involves wide surgical excision followed by adjuvant radiotherapy. "
    "Prognosis remains poor despite aggressive multimodal therapy. "
    "This case report describes a 78-year-old man with biopsy-confirmed scalp angiosarcoma. "
    "FDG-PET was used both for staging and for radiotherapy planning in this patient. "
    "Follow-up imaging six months later showed no evidence of nodal or distant metastasis."
)


def test_compression_keeps_most_query_relevant_sentences():
    query = "scalp angiosarcoma FDG-PET"
    result = compress_abstract(query, _LONG_ABSTRACT, top_n=3)

    assert not result.skipped
    assert result.sentences_kept == 3
    # The two sentences mentioning FDG-PET plus the disease-defining first
    # sentence should heavily outscore purely-prognosis/treatment sentences.
    assert "FDG-PET imaging shows markedly increased uptake" in result.text
    assert "Scalp angiosarcoma is a rare and aggressive vascular malignancy" in result.text
    # A low-overlap sentence should have been dropped.
    assert "Prognosis remains poor" not in result.text


def test_compression_reduces_token_count():
    query = "scalp angiosarcoma FDG-PET"
    result = compress_abstract(query, _LONG_ABSTRACT, top_n=3)
    assert result.tokens_after < result.tokens_before
    assert result.tokens_saved > 0
    assert result.reduction_pct > 0


def test_compression_preserves_original_sentence_order():
    query = "FDG-PET staging"
    result = compress_abstract(query, _LONG_ABSTRACT, top_n=3)
    # "FDG-PET imaging shows..." (idx 2) must precede "FDG-PET was used..." (idx 6)
    # in the compressed output even though the scorer may rank them differently.
    idx_first = result.text.find("FDG-PET imaging shows")
    idx_second = result.text.find("FDG-PET was used")
    assert idx_first != -1 and idx_second != -1
    assert idx_first < idx_second


def test_compression_degrades_to_full_text_when_too_few_sentences():
    short_abstract = "A rare case. FDG-PET showed uptake."
    result = compress_abstract("FDG-PET rare case", short_abstract, top_n=4)
    assert result.skipped is True
    assert result.text == short_abstract
    assert result.tokens_after == result.tokens_before


def test_compression_degrades_when_sentence_count_at_or_below_top_n():
    # Exactly top_n sentences -- nothing to trim, should be a no-op/skip.
    abstract = "One. Two words here. Three is the last sentence in this test."
    result = compress_abstract("one two three", abstract, top_n=3)
    assert result.skipped is True
    assert result.text == abstract


def test_compress_papers_for_prompt_never_breaks_citation_alignment():
    query = "FDG-PET scalp"
    other_abstract = (
        "Progressive supranuclear palsy involves midbrain atrophy. "
        "PET imaging often shows characteristic midbrain hypometabolism. "
        "Vertical gaze palsy is a classic clinical feature. "
        "Postural instability and early falls are common. "
        "Response to levodopa is typically poor or absent."
    )
    papers = [("PMID1", _LONG_ABSTRACT), ("PMID2", other_abstract)]
    compressed = compress_papers_for_prompt(query, papers, top_n=3)

    assert [c.pmid for c in compressed] == ["PMID1", "PMID2"]
    # Each paper's compressed text must only contain content from its own
    # abstract -- no cross-paper sentence bleed when a caller concatenates
    # these into one multi-paper prompt and tags each block with its pmid.
    pmid1_text = compressed[0].result.text
    pmid2_text = compressed[1].result.text
    assert "midbrain" not in pmid1_text.lower()
    assert "angiosarcoma" not in pmid2_text.lower()


def test_aggregate_reduction_pct_weighted_not_averaged():
    r1 = CompressionResult(text="", sentences_kept=1, sentences_total=5,
                            tokens_before=100, tokens_after=50, skipped=False)
    r2 = CompressionResult(text="", sentences_kept=1, sentences_total=5,
                            tokens_before=10, tokens_after=8, skipped=False)
    # Weighted: (100-50 + 10-8) / (100+10) = 52/110 = 47.27%
    # Simple average of (50%, 20%) would be 35% -- must NOT match that.
    pct = aggregate_reduction_pct([r1, r2])
    assert pct == round(100.0 * 52 / 110, 2)


def test_aggregate_reduction_pct_empty_list():
    assert aggregate_reduction_pct([]) == 0.0
