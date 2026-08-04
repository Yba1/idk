from backend.app.retrieval.rarity import rarity_boost
from backend.app.retrieval.hybrid import HybridRetriever

PAPERS = [
    {"pmid": "1", "title": "Scalp angiosarcoma PET case report", "abstract": "Rare vascular tumor, focal FDG uptake.", "rarity": "rare"},
    {"pmid": "2", "title": "Alzheimer's disease FDG-PET", "abstract": "Common bilateral temporal parietal hypometabolism.", "rarity": "common"},
    {"pmid": "3", "title": "Another Alzheimer's disease PET study", "abstract": "Common typical dementia pattern imaging.", "rarity": "common"},
]


def test_rarity_boost_favors_rare():
    assert rarity_boost({"rarity": "rare"}) > rarity_boost({"rarity": "common"})


def test_hybrid_search_with_rarity_surfaces_rare_case():
    retriever = HybridRetriever(PAPERS)
    weighted = retriever.search("uptake pattern in brain imaging", top_k=3, apply_rarity=True)
    naive = retriever.search("uptake pattern in brain imaging", top_k=3, apply_rarity=False)

    naive_rank_of_rare = next(i for i, (p, s) in enumerate(naive) if p["pmid"] == "1")
    weighted_rank_of_rare = next(i for i, (p, s) in enumerate(weighted) if p["pmid"] == "1")

    assert weighted_rank_of_rare <= naive_rank_of_rare


def test_hybrid_search_handles_empty_corpus():
    retriever = HybridRetriever([])
    assert retriever.search("any query", top_k=5) == []


def test_hybrid_search_tied_scores_returns_all_papers_without_crashing():
    tied_papers = [
        {"pmid": "1", "title": "Identical PET finding report", "abstract": "Identical PET finding report.", "rarity": "common"},
        {"pmid": "2", "title": "Identical PET finding report", "abstract": "Identical PET finding report.", "rarity": "common"},
    ]
    retriever = HybridRetriever(tied_papers)
    results = retriever.search("identical PET finding report", top_k=2)
    assert {p["pmid"] for p, _ in results} == {"1", "2"}


def test_rarity_boost_formula_exact_values():
    """Test that rarity_boost returns the exact configured multipliers."""
    from backend.app.retrieval.rarity import RARE_BOOST, COMMON_BOOST

    rare_paper = {"rarity": "rare"}
    common_paper = {"rarity": "common"}

    assert rarity_boost(rare_paper) == RARE_BOOST
    assert rarity_boost(common_paper) == COMMON_BOOST
    assert RARE_BOOST == 1.6
    assert COMMON_BOOST == 1.0
    assert rarity_boost(rare_paper) / rarity_boost(common_paper) == 1.6


def test_rarity_boost_missing_rarity_field():
    """Test that papers without rarity field default to common boost."""
    paper_without_rarity = {"pmid": "test"}
    assert rarity_boost(paper_without_rarity) == rarity_boost({"rarity": "common"})


def test_hybrid_search_with_larger_mixed_corpus():
    """Test hybrid ranking with a more realistic 10-paper corpus mixing rarity and relevance."""
    corpus = [
        # Rare cases - high precision but may have lower relevance signal
        {"pmid": "rare_1", "title": "Scalp angiosarcoma PET case", "abstract": "Rare vascular tumor with focal FDG uptake at scalp.", "rarity": "rare"},
        {"pmid": "rare_2", "title": "Cutaneous lymphoma imaging", "abstract": "Unusual cutaneous lymphoma with abnormal PET signal.", "rarity": "rare"},
        {"pmid": "rare_3", "title": "Embryonal carcinoma PET", "abstract": "Rare embryonal tumor imaging findings.", "rarity": "rare"},
        # Common cases - high relevance signal but common findings
        {"pmid": "common_1", "title": "Alzheimer's disease FDG-PET", "abstract": "Common bilateral temporal parietal hypometabolism pattern.", "rarity": "common"},
        {"pmid": "common_2", "title": "Parkinson's disease imaging", "abstract": "Typical putaminal hypodensity on common PET imaging.", "rarity": "common"},
        {"pmid": "common_3", "title": "Depression and PET imaging", "abstract": "Common prefrontal cortex hypometabolism in depression.", "rarity": "common"},
        {"pmid": "common_4", "title": "Schizophrenia neuroimaging", "abstract": "Common thalamic and cortical abnormalities on PET.", "rarity": "common"},
        # Mixed relevance/rarity
        {"pmid": "mixed_1", "title": "Meningioma PET findings", "abstract": "Meningioma with variable FDG uptake patterns.", "rarity": "common"},
        {"pmid": "mixed_2", "title": "Glioblastoma imaging markers", "abstract": "Glioblastoma with high FDG uptake.", "rarity": "common"},
        {"pmid": "exotic", "title": "Prion disease case series", "abstract": "Rare prion disease with characteristic PET pattern.", "rarity": "rare"},
    ]

    retriever = HybridRetriever(corpus)

    # Query that should match several papers
    weighted_results = retriever.search("PET FDG uptake imaging", top_k=5, apply_rarity=True)
    unweighted_results = retriever.search("PET FDG uptake imaging", top_k=5, apply_rarity=False)

    # Verify we got results
    assert len(weighted_results) == 5
    assert len(unweighted_results) == 5

    # Extract PMIDs
    weighted_pmids = [p["pmid"] for p, _ in weighted_results]
    unweighted_pmids = [p["pmid"] for p, _ in unweighted_results]

    # With rarity weighting, at least some rare cases should appear in top 5
    rare_pmids_in_weighted = [pmid for pmid in weighted_pmids if pmid.startswith("rare_")]
    assert len(rare_pmids_in_weighted) > 0, "Rarity weighting should surface rare cases"

    # Verify results are ranked (descending scores)
    weighted_scores = [score for _, score in weighted_results]
    assert all(weighted_scores[i] >= weighted_scores[i + 1] for i in range(len(weighted_scores) - 1))


def test_weighted_merge_keeps_strong_raw_query_match_above_hyde_only_match():
    """Test that 0.6/0.4 weighted merge keeps a paper strong on raw query ranked
    above a paper only a fabricated HyDE text would favor."""
    corpus = [
        # Paper 1: Strong match for raw query "scalp angiosarcoma"
        {"pmid": "scalp_strong", "title": "Scalp angiosarcoma PET imaging", "abstract": "Cutaneous scalp angiosarcoma with FDG PET findings.", "rarity": "rare"},
        # Paper 2: Weak on raw query "scalp angiosarcoma" but might match a fabricated HyDE case about dementia
        {"pmid": "dementia_weak", "title": "Dementia and PET findings", "abstract": "Cognitive decline with temporal lobe hypometabolism.", "rarity": "common"},
    ]

    retriever = HybridRetriever(corpus)

    # Simulate raw query being strong on paper 1, weak on paper 2
    # and HyDE text being weak on paper 1, strong on paper 2
    raw_query_results = retriever.search("scalp angiosarcoma", top_k=2)
    hyde_results = retriever.search("hypothetical dementia case report", top_k=2)

    # Raw query should rank scalp_strong higher
    raw_rank_scalp = next((i for i, (p, _) in enumerate(raw_query_results) if p["pmid"] == "scalp_strong"), None)
    raw_rank_dementia = next((i for i, (p, _) in enumerate(raw_query_results) if p["pmid"] == "dementia_weak"), None)
    assert raw_rank_scalp < raw_rank_dementia, "Raw query should rank scalp_strong higher"

    # Weighted merge with both queries
    merged_results = retriever.search("scalp angiosarcoma", secondary_query="hypothetical dementia case report", top_k=2)

    # Even with HyDE strong on dementia, weighted merge (0.6 raw + 0.4 hyde) should keep scalp_strong on top
    merged_rank_scalp = next((i for i, (p, _) in enumerate(merged_results) if p["pmid"] == "scalp_strong"), None)
    merged_rank_dementia = next((i for i, (p, _) in enumerate(merged_results) if p["pmid"] == "dementia_weak"), None)
    assert merged_rank_scalp < merged_rank_dementia, "Weighted merge should prioritize raw query match"
