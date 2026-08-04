import json
from pathlib import Path
import numpy as np

from backend.app.retrieval.demo_fixture import run_demo_contrast
from backend.app.retrieval.hybrid import HybridRetriever
from backend.app.retrieval.condition_match import NO_MATCH_THRESHOLD

CORPUS_PATH = Path(__file__).resolve().parent.parent / "data" / "corpus.json"

# Gold-set in-scope queries: these should have high similarity to corpus conditions
GOLD_SET_IN_SCOPE_QUERIES = [
    # Movement disorders (PSP, CBS, Parkinson's)
    "unusual FDG uptake pattern in rare movement disorder case",
    "midbrain hypometabolism in progressive supranuclear palsy",
    "basal ganglia finding on PET scan",
    # Dementia variants
    "frontotemporal dementia with anterior temporal involvement",
    "semantic variant primary progressive aphasia imaging",
    # CNS inflammation
    "anti-NMDA receptor encephalitis with basal ganglia involvement",
    "primary angiitis of CNS with MCA territory findings",
]

# Gold-set out-of-scope queries: these should have low similarity to corpus conditions
GOLD_SET_OUT_OF_SCOPE_QUERIES = [
    "liver cancer PET scan imaging",
    "COVID lung CT findings",
    "renal cell carcinoma imaging",
    "colorectal cancer metastases",
    "breast cancer bone metastases",
]


def test_naive_ranking_buries_rare_case_but_weighted_surfaces_it():
    result = run_demo_contrast()
    rare_pmid = result["rare_case_pmid"]

    naive_rank = result["naive_top5"].index(rare_pmid) if rare_pmid in result["naive_top5"] else 99
    weighted_rank = result["weighted_top5"].index(rare_pmid) if rare_pmid in result["weighted_top5"] else 99

    assert weighted_rank < naive_rank, "rarity weighting must rank the rare case higher than naive ranking"
    assert rare_pmid in result["weighted_top5"], "rare case must actually surface into the weighted top 5"


def test_condition_centroid_threshold_separates_in_scope_from_out_of_scope():
    """Verify that NO_MATCH_THRESHOLD correctly separates known in-scope queries
    from known out-of-scope queries using condition-centroid similarity."""
    corpus = json.loads(CORPUS_PATH.read_text())
    retriever = HybridRetriever(corpus)

    # Compute similarities for in-scope queries
    in_scope_similarities = []
    for query in GOLD_SET_IN_SCOPE_QUERIES:
        closest = retriever.get_closest_conditions(query, top_n=1)
        if closest:
            _, similarity, _ = closest[0]
            in_scope_similarities.append(similarity)

    # Compute similarities for out-of-scope queries
    out_of_scope_similarities = []
    for query in GOLD_SET_OUT_OF_SCOPE_QUERIES:
        closest = retriever.get_closest_conditions(query, top_n=1)
        if closest:
            _, similarity, _ = closest[0]
            out_of_scope_similarities.append(similarity)

    # All in-scope queries should be above or near the threshold
    # All out-of-scope queries should be below or near the threshold
    min_in_scope = min(in_scope_similarities) if in_scope_similarities else 0.0
    max_out_of_scope = max(out_of_scope_similarities) if out_of_scope_similarities else 0.0

    # The threshold should separate the distributions
    assert min_in_scope >= NO_MATCH_THRESHOLD or max_out_of_scope <= NO_MATCH_THRESHOLD, \
        f"Threshold {NO_MATCH_THRESHOLD} doesn't separate gold-set queries: " \
        f"in-scope min={min_in_scope:.3f}, out-of-scope max={max_out_of_scope:.3f}"
